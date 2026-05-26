import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.deps import AuthToken, DbSession
from api.schemas.generation_log import GenerationLogRead
from api.schemas.video import VideoDetail, VideoRead
from models.topic import Topic, TopicStatus
from models.video import Video, VideoStatus


def _with_topic_title(video: Video, topic_title: str | None) -> VideoRead:
    data = VideoRead.model_validate(video)
    data.topic_title = topic_title
    return data

router = APIRouter()

_CHUNK = 1024 * 1024  # 1 MB streaming chunk


@router.get("", response_model=list[VideoRead])
async def list_videos(
    db: DbSession,
    _: AuthToken,
    channel_id: int | None = Query(None),
    status: VideoStatus | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    from sqlalchemy import join
    stmt = select(Video, Topic.title.label("topic_title")).join(
        Topic, Topic.id == Video.topic_id, isouter=True
    )
    if channel_id:
        stmt = stmt.where(Video.channel_id == channel_id)
    if status:
        stmt = stmt.where(Video.status == status)
    stmt = stmt.order_by(Video.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.all()
    out = []
    for row in rows:
        v, t_title = row[0], row[1]
        d = VideoRead.model_validate(v)
        d.topic_title = t_title
        out.append(d)
    return out


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: int, db: DbSession, _: AuthToken):
    from sqlalchemy import join
    result = await db.execute(
        select(Video, Topic.title.label("topic_title")).join(
            Topic, Topic.id == Video.topic_id, isouter=True
        ).where(Video.id == video_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    v, t_title = row[0], row[1]
    d = VideoDetail.model_validate(v)
    d.topic_title = t_title
    return d


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: int, db: DbSession, _: AuthToken):
    """Delete video, its generation logs, local files, and associated topic."""
    import shutil
    from sqlalchemy import delete as sa_delete
    from config import get_settings
    from models.generation_log import GenerationLog
    from models.topic import Topic

    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete local files first
    try:
        vid_dir = Path(get_settings().storage_path) / str(video_id)
        if vid_dir.exists():
            shutil.rmtree(vid_dir, ignore_errors=True)
    except Exception:
        pass

    topic_id = v.topic_id

    # Delete in correct order to satisfy FK constraints
    await db.execute(sa_delete(GenerationLog).where(GenerationLog.video_id == video_id))
    await db.execute(sa_delete(Video).where(Video.id == video_id))
    await db.flush()

    # Delete the topic too
    topic = await db.get(Topic, topic_id)
    if topic:
        await db.delete(topic)


@router.get("/{video_id}/preview")
async def preview_video(video_id: int, db: DbSession, _: AuthToken):
    v = await db.get(Video, video_id)
    if not v or not v.final_video_path:
        raise HTTPException(status_code=404, detail="Video file not found")
    path = Path(v.final_video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file missing from storage")
    file_size = path.stat().st_size

    def _iter():
        with open(path, "rb") as fh:
            while chunk := fh.read(_CHUNK):
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{video_id}/logs", response_model=list[GenerationLogRead])
async def get_video_logs(video_id: int, db: DbSession, _: AuthToken):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    from sqlalchemy import select
    from models.generation_log import GenerationLog
    result = await db.execute(
        select(GenerationLog)
        .where(GenerationLog.video_id == video_id)
        .order_by(GenerationLog.id)
    )
    return [GenerationLogRead.model_validate(log) for log in result.scalars().all()]


@router.post("/{video_id}/publish", response_model=VideoRead)
async def publish_video(video_id: int, db: DbSession, _: AuthToken):
    """Trigger manual YouTube upload for a finished video."""
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    if v.youtube_video_id:
        raise HTTPException(status_code=400, detail="Already uploaded to YouTube")
    if v.status == VideoStatus.uploading:
        raise HTTPException(status_code=400, detail="Upload already in progress")
    if v.status not in (VideoStatus.done, VideoStatus.failed):
        raise HTTPException(status_code=400, detail="Video must be done before uploading")
    if not v.final_video_path:
        raise HTTPException(status_code=400, detail="Video file not found — regenerate first")

    from models.channel import Channel
    channel = await db.get(Channel, v.channel_id)
    if not channel or not channel.refresh_token_encrypted:
        raise HTTPException(status_code=400, detail="Channel has no YouTube OAuth credentials")

    from workers.tasks import upload_video_to_youtube
    v.status = VideoStatus.uploading
    v.error_message = None
    await db.flush()
    await db.refresh(v)

    upload_video_to_youtube.delay(video_id)
    return VideoRead.model_validate(v)


@router.post("/{video_id}/retry", response_model=VideoRead)
async def retry_video(video_id: int, db: DbSession, _: AuthToken):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    if v.status != VideoStatus.failed:
        raise HTTPException(status_code=400, detail="Only failed videos can be retried")

    topic = await db.get(__import__("models.topic", fromlist=["Topic"]).Topic, v.topic_id)
    topic.status = TopicStatus.pending
    topic.error_message = None
    v.status = VideoStatus.pending
    v.error_message = None
    await db.flush()
    await db.refresh(v)

    from workers.tasks import process_topic
    process_topic.delay(v.topic_id)
    return VideoRead.model_validate(v)
