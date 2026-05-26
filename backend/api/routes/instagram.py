"""Instagram OAuth + publish endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from api.deps import AuthToken, DbSession
from config import get_settings

router = APIRouter()
settings = get_settings()


# ── /oauth-callback MUST be defined before /{channel_id} ──────────────────────

@router.get("/oauth-callback")
async def instagram_oauth_callback_static(
    code: str = Query(...),
    state: str = Query(...),
):
    """Facebook OAuth redirect — saves Instagram token to channel."""
    from db.session import async_session_factory
    from models.channel import Channel
    from pipeline.instagram_upload import exchange_instagram_code

    channel_id = int(state)
    async with async_session_factory() as session:
        ch = await session.get(Channel, channel_id)
        if not ch:
            return RedirectResponse(url="/?error=channel_not_found")
        try:
            tokens = exchange_instagram_code(code=code, channel_id=channel_id)
        except Exception as exc:
            return RedirectResponse(url=f"/channels?error=instagram_oauth_failed&msg={str(exc)[:80]}")
        ch.instagram_user_id = tokens["instagram_user_id"]
        ch.instagram_access_token_encrypted = tokens["instagram_access_token_encrypted"]
        await session.commit()
    return RedirectResponse(url=f"/channels?instagram=success&channel={channel_id}")


@router.get("/{channel_id}/auth-url")
async def instagram_auth_url(channel_id: int, db: DbSession, _: AuthToken) -> dict:
    """Return Facebook OAuth URL to get Instagram publishing token."""
    from models.channel import Channel
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not settings.meta_app_id:
        raise HTTPException(
            status_code=400,
            detail="META_APP_ID not configured. Add it to .env and restart.",
        )
    from pipeline.instagram_upload import get_instagram_auth_url
    return {"auth_url": get_instagram_auth_url(channel_id)}


@router.get("/oauth-callback")
async def instagram_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Facebook OAuth redirect — saves Instagram token to channel."""
    from db.session import async_session_factory
    from models.channel import Channel
    from pipeline.instagram_upload import exchange_instagram_code

    channel_id = int(state)
    async with async_session_factory() as session:
        ch = await session.get(Channel, channel_id)
        if not ch:
            return RedirectResponse(url="/?error=channel_not_found")
        try:
            tokens = exchange_instagram_code(code=code, channel_id=channel_id)
        except Exception as exc:
            return RedirectResponse(url=f"/?error=instagram_oauth_failed&msg={str(exc)[:100]}")
        ch.instagram_user_id = tokens["instagram_user_id"]
        ch.instagram_access_token_encrypted = tokens["instagram_access_token_encrypted"]
        await session.commit()
    return RedirectResponse(url=f"/channels?instagram=success&channel={channel_id}")


@router.post("/{channel_id}/publish/{video_id}")
async def publish_to_instagram(
    channel_id: int,
    video_id: int,
    db: DbSession,
    _: AuthToken,
) -> dict:
    """Manually publish an existing video to Instagram Reels."""
    from models.channel import Channel
    from models.video import Video, VideoStatus

    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not ch.instagram_user_id or not ch.instagram_access_token_encrypted:
        raise HTTPException(status_code=400, detail="Instagram not connected on this channel")

    video = await db.get(Video, video_id)
    if not video or not video.final_video_path:
        raise HTTPException(status_code=404, detail="Video not found or not assembled yet")

    from pipeline.instagram_upload import upload_reels
    try:
        result = upload_reels(
            channel=ch,
            video_id=video_id,
            caption=video.script_description or video.script_title or "",
            hashtags=list(video.script_tags or []) + list(ch.default_tags or []),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    video.instagram_media_id = result["instagram_media_id"]
    video.instagram_url = result["instagram_url"]
    video.instagram_published_at = datetime.now(timezone.utc)
    await db.flush()

    return result
