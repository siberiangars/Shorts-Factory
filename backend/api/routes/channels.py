import json
from datetime import datetime, timezone

import anthropic
import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from api.deps import AuthToken, DbSession
from api.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from api.schemas.topic import TopicCreate, TopicRead
from config import get_settings
from models.channel import Channel
from models.topic import Topic, TopicStatus
from utils.crypto import decrypt, encrypt

log = structlog.get_logger()
router = APIRouter()
settings = get_settings()


def _to_read(ch: Channel) -> ChannelRead:
    return ChannelRead(
        **{c.name: getattr(ch, c.name) for c in ch.__table__.columns
           if c.name not in ("refresh_token_encrypted", "access_token_encrypted",
                             "instagram_access_token_encrypted")},
        has_oauth=bool(ch.refresh_token_encrypted),
        has_instagram=bool(ch.instagram_access_token_encrypted),
    )


# ── Static paths FIRST (must come before /{channel_id} to avoid greedy matching) ──

@router.get("/oauth-callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    """Google OAuth redirect — exchanges code for tokens, saves encrypted to DB."""
    from pipeline.youtube_upload import exchange_code_for_tokens
    from db.session import async_session_factory
    channel_id = int(state)
    async with async_session_factory() as session:
        ch = await session.get(Channel, channel_id)
        if not ch:
            return RedirectResponse(url="/?error=channel_not_found")
        try:
            tokens = exchange_code_for_tokens(code=code, channel_id=channel_id)
        except Exception as exc:
            log.error("oauth_callback_failed", channel_id=channel_id, error=str(exc))
            return RedirectResponse(url=f"/?error=oauth_failed&msg={str(exc)[:80]}")
        ch.refresh_token_encrypted = tokens["refresh_token_encrypted"]
        ch.access_token_encrypted = tokens["access_token_encrypted"]
        ch.token_expires_at = tokens["token_expires_at"]
        await session.commit()
    return RedirectResponse(url=f"/channels?oauth=success&channel={channel_id}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
async def create_channel(body: ChannelCreate, db: DbSession, _: AuthToken):
    ch = Channel(**body.model_dump())
    db.add(ch)
    await db.flush()
    await db.refresh(ch)
    return _to_read(ch)


@router.get("", response_model=list[ChannelRead])
async def list_channels(db: DbSession, _: AuthToken):
    result = await db.execute(__import__("sqlalchemy").select(Channel))
    return [_to_read(c) for c in result.scalars().all()]


@router.get("/{channel_id}", response_model=ChannelRead)
async def get_channel(channel_id: int, db: DbSession, _: AuthToken):
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _to_read(ch)


@router.patch("/{channel_id}", response_model=ChannelRead)
async def update_channel(channel_id: int, body: ChannelUpdate, db: DbSession, _: AuthToken):
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ch, field, value)
    await db.flush()
    await db.refresh(ch)
    return _to_read(ch)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: int, db: DbSession, _: AuthToken):
    from sqlalchemy import select, delete as sa_delete
    from models.topic import Topic
    from models.video import Video
    from models.generation_log import GenerationLog

    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get all topics for this channel
    topics_result = await db.execute(select(Topic).where(Topic.channel_id == channel_id))
    topic_ids = [t.id for t in topics_result.scalars().all()]

    if topic_ids:
        # Get all videos for these topics
        videos_result = await db.execute(select(Video).where(Video.topic_id.in_(topic_ids)))
        video_ids = [v.id for v in videos_result.scalars().all()]

        if video_ids:
            # Delete generation logs
            await db.execute(sa_delete(GenerationLog).where(GenerationLog.video_id.in_(video_ids)))
            # Delete videos
            await db.execute(sa_delete(Video).where(Video.id.in_(video_ids)))

        # Delete topics
        await db.execute(sa_delete(Topic).where(Topic.id.in_(topic_ids)))

    await db.flush()
    await db.delete(ch)


# ── Auth-url (after static, before nothing) ───────────────────────────────────

@router.get("/{channel_id}/auth-url")
async def get_auth_url(channel_id: int, db: DbSession, _: AuthToken) -> dict:
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    from pipeline.youtube_upload import get_auth_url
    try:
        url = get_auth_url(channel_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not build auth URL: {exc}")
    return {"auth_url": url}


# ── AI topic generation ───────────────────────────────────────────────────────

@router.post("/{channel_id}/generate-topics", response_model=list[TopicRead])
async def generate_topics(channel_id: int, db: DbSession, _: AuthToken):
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Generate 20 unique YouTube Shorts topic ideas for a channel about: {ch.niche}.\n"
        f"Language: {ch.language}. Topics must be specific, data-driven, health-related.\n"
        "Return ONLY a JSON array of strings, no markdown:\n"
        '["Topic 1", "Topic 2", ...]'
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        titles: list[str] = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Claude error: {exc}")

    topics = []
    for title in titles[:20]:
        t = Topic(channel_id=channel_id, title=title, status=TopicStatus.pending)
        db.add(t)
        topics.append(t)
    await db.flush()
    for t in topics:
        await db.refresh(t)
    return [TopicRead.model_validate(t) for t in topics]
