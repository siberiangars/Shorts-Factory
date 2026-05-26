"""
Instagram Reels publishing via Instagram Graph API.

Flow:
  1. Create Reels container  POST /{ig_user_id}/media
  2. Poll status             GET /{ig_user_id}/media?fields=status_code until FINISHED
  3. Publish                 POST /{ig_user_id}/media_publish

Requirements:
  - Instagram Professional account (Creator or Business)
  - Facebook App with instagram_content_publish + instagram_basic permissions
  - Access token with those scopes
  - Publicly accessible video URL (HTTPS preferred)
"""
import time
from typing import TYPE_CHECKING, Literal

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.crypto import decrypt, encrypt

if TYPE_CHECKING:
    from models.channel import Channel

log = structlog.get_logger()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
POLL_INTERVAL = 10
MAX_POLLS = 60  # 10 minutes


def _get_access_token(channel: "Channel") -> str:
    if not channel.instagram_access_token_encrypted:
        raise PipelineError(
            "instagram_upload",
            f"Channel {channel.id} has no Instagram access token — run OAuth first",
        )
    return decrypt(channel.instagram_access_token_encrypted)


def _get_video_public_url(video_id: int) -> str:
    """Build the public URL for the video file served by our API."""
    settings = get_settings()
    return f"{settings.storage_base_url}/api/videos/{video_id}/preview"


def upload_reels(
    channel: "Channel",
    video_id: int,
    caption: str,
    hashtags: list[str],
    share_to_feed: bool = True,
) -> dict:
    """
    Upload a finished video as an Instagram Reel.
    Returns {'instagram_media_id': str, 'instagram_url': str}.
    """
    access_token = _get_access_token(channel)
    ig_user_id = channel.instagram_user_id
    if not ig_user_id:
        raise PipelineError(
            "instagram_upload",
            f"Channel {channel.id} has no instagram_user_id",
        )

    video_url = _get_video_public_url(video_id)

    # Build caption with hashtags
    tag_str = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
    full_caption = f"{caption}\n\n{tag_str}".strip()

    # ── 1. Create media container ─────────────────────────────────────────────
    try:
        resp = requests.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": full_caption,
                "share_to_feed": str(share_to_feed).lower(),
                "access_token": access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise PipelineError("instagram_upload", f"Create container failed: {exc}", exc)

    if "error" in data:
        raise PipelineError("instagram_upload", f"Instagram API error: {data['error'].get('message', data['error'])}")

    container_id: str = data["id"]
    log.info("instagram_container_created", container_id=container_id)

    # ── 2. Poll until container is ready ─────────────────────────────────────
    for attempt in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        try:
            st_resp = requests.get(
                f"{GRAPH_BASE}/{container_id}",
                params={"fields": "status_code,status", "access_token": access_token},
                timeout=30,
            )
            st_resp.raise_for_status()
            st_data = st_resp.json()
        except requests.RequestException as exc:
            log.warning("instagram_poll_error", attempt=attempt, error=str(exc))
            continue

        status_code = st_data.get("status_code", "")
        log.info("instagram_poll", container_id=container_id, status=status_code, attempt=attempt)

        if status_code == "FINISHED":
            break
        elif status_code in ("ERROR", "EXPIRED"):
            raise PipelineError(
                "instagram_upload",
                f"Container {container_id} failed with status: {status_code}",
            )
    else:
        raise PipelineError(
            "instagram_upload",
            f"Instagram container {container_id} timed out",
        )

    # ── 3. Publish ────────────────────────────────────────────────────────────
    try:
        pub_resp = requests.post(
            f"{GRAPH_BASE}/{ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token,
            },
            timeout=30,
        )
        pub_resp.raise_for_status()
        pub_data = pub_resp.json()
    except requests.RequestException as exc:
        raise PipelineError("instagram_upload", f"Publish failed: {exc}", exc)

    media_id: str = pub_data["id"]
    ig_url = f"https://www.instagram.com/p/{media_id}/"
    log.info("instagram_published", media_id=media_id, url=ig_url)
    return {"instagram_media_id": media_id, "instagram_url": ig_url}


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def get_instagram_auth_url(channel_id: int) -> str:
    """Build Facebook OAuth URL for Instagram publishing permissions."""
    settings = get_settings()
    import urllib.parse
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.instagram_oauth_redirect_uri,
        "scope": "instagram_basic,instagram_content_publish,pages_read_engagement",
        "response_type": "code",
        "state": str(channel_id),
    }
    return "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params)


def exchange_instagram_code(code: str, channel_id: int) -> dict:
    """Exchange auth code for long-lived token + Instagram user ID."""
    settings = get_settings()

    # 1. Short-lived token
    resp = requests.post(
        f"{GRAPH_BASE}/oauth/access_token",
        data={
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": settings.instagram_oauth_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    short_token = resp.json()["access_token"]

    # 2. Exchange for long-lived token (60 days)
    ll_resp = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    ll_resp.raise_for_status()
    long_token = ll_resp.json()["access_token"]

    # 3. Get Instagram Business Account ID
    pages_resp = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={"access_token": long_token},
        timeout=30,
    )
    pages_resp.raise_for_status()
    pages = pages_resp.json().get("data", [])
    if not pages:
        raise PipelineError("instagram_upload", "No Facebook Pages found for this account")

    page_token = pages[0]["access_token"]
    page_id = pages[0]["id"]

    # 4. Get Instagram Business Account linked to the page
    ig_resp = requests.get(
        f"{GRAPH_BASE}/{page_id}",
        params={"fields": "instagram_business_account", "access_token": page_token},
        timeout=30,
    )
    ig_resp.raise_for_status()
    ig_data = ig_resp.json()
    ig_account = ig_data.get("instagram_business_account", {})
    if not ig_account:
        raise PipelineError(
            "instagram_upload",
            "No Instagram Business account linked to this Facebook Page",
        )

    return {
        "instagram_access_token_encrypted": encrypt(long_token),
        "instagram_user_id": ig_account["id"],
    }
