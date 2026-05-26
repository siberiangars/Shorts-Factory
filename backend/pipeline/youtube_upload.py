from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import get_settings
from pipeline.errors import PipelineError
from utils.crypto import decrypt, encrypt

if TYPE_CHECKING:
    from models.channel import Channel

log = structlog.get_logger()

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def _get_credentials(channel: "Channel") -> Credentials:
    """Decrypt stored tokens and refresh if needed."""
    if not channel.refresh_token_encrypted:
        raise PipelineError(
            "youtube_upload", f"Channel {channel.id} has no refresh token — run OAuth first"
        )
    settings = get_settings()
    refresh_token = decrypt(channel.refresh_token_encrypted)
    access_token = (
        decrypt(channel.access_token_encrypted) if channel.access_token_encrypted else None
    )
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_get_client_id(settings),
        client_secret=_get_client_secret(settings),
        scopes=_SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
    return creds


def _get_client_id(settings) -> str:
    import json
    with open(settings.youtube_client_secrets_file) as fh:
        data = json.load(fh)
    return data.get("web", data.get("installed", {}))["client_id"]


def _get_client_secret(settings) -> str:
    import json
    with open(settings.youtube_client_secrets_file) as fh:
        data = json.load(fh)
    return data.get("web", data.get("installed", {}))["client_secret"]


def upload_short(
    channel: "Channel",
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: Literal["private", "unlisted", "public"] = "unlisted",
) -> dict:
    """Upload video to YouTube, return video_id and URL."""
    if "#Shorts" not in title and "#shorts" not in title:
        title = f"{title} #Shorts"

    try:
        creds = _get_credentials(channel)
    except Exception as exc:
        raise PipelineError("youtube_upload", f"Credential error: {exc}", exc)

    try:
        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],  # YouTube max
                "description": description,
                "tags": tags,
                "categoryId": "26",  # How-to & Style
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(
            str(video_path), mimetype="video/mp4", resumable=True, chunksize=_CHUNK_SIZE
        )
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response["id"]
        url = f"https://www.youtube.com/shorts/{video_id}"
        log.info("youtube_uploaded", channel_id=channel.id, video_id=video_id, privacy=privacy)
        return {"youtube_video_id": video_id, "youtube_url": url, "quota_used": 1600}

    except Exception as exc:
        raise PipelineError("youtube_upload", f"Upload failed: {exc}", exc)


def get_auth_url(channel_id: int) -> str:
    """Build Google OAuth consent URL — manual build WITHOUT PKCE to allow stateless exchange."""
    import urllib.parse
    import json as _json
    settings = get_settings()
    with open(settings.youtube_client_secrets_file) as fh:
        secret = _json.load(fh)
    client_id = secret.get("web", secret.get("installed", {}))["client_id"]
    params = {
        "client_id": client_id,
        "redirect_uri": settings.youtube_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "state": str(channel_id),
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code: str, channel_id: int) -> dict:
    """Exchange OAuth code → tokens via plain HTTP POST (no PKCE, stateless)."""
    import json as _json
    import requests as _req
    from datetime import datetime, timezone, timedelta
    settings = get_settings()
    with open(settings.youtube_client_secrets_file) as fh:
        secret = _json.load(fh)
    cd = secret.get("web", secret.get("installed", {}))

    resp = _req.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": cd["client_id"],
            "client_secret": cd["client_secret"],
            "redirect_uri": settings.youtube_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()

    if "error" in tokens:
        raise PipelineError("youtube_oauth", f"Token exchange error: {tokens['error_description']}")

    expiry = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
    return {
        "refresh_token_encrypted": encrypt(tokens["refresh_token"]) if tokens.get("refresh_token") else None,
        "access_token_encrypted": encrypt(tokens["access_token"]) if tokens.get("access_token") else None,
        "token_expires_at": expiry,
    }
