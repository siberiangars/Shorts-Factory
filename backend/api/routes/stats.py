from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from api.deps import AuthToken, DbSession
from api.schemas.stats import StatsRead
from models.video import Video, VideoStatus

router = APIRouter()

_IN_PROGRESS_STATUSES = [
    VideoStatus.generating_script,
    VideoStatus.generating_voice,
    VideoStatus.fetching_broll,
    VideoStatus.transcribing,
    VideoStatus.assembling,
    VideoStatus.uploading,
]


@router.get("", response_model=StatsRead)
async def get_stats(db: DbSession, _: AuthToken):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    pending_result = await db.execute(
        select(func.count(Video.id)).where(Video.status == VideoStatus.pending)
    )
    in_progress_result = await db.execute(
        select(func.count(Video.id)).where(Video.status.in_(_IN_PROGRESS_STATUSES))
    )
    done_today_result = await db.execute(
        select(func.count(Video.id)).where(
            Video.status == VideoStatus.done,
            Video.published_at >= today_start,
        )
    )
    done_total_result = await db.execute(
        select(func.count(Video.id)).where(Video.status == VideoStatus.done)
    )
    avg_cost_result = await db.execute(
        select(func.avg(Video.generation_cost_usd)).where(Video.status == VideoStatus.done)
    )

    return StatsRead(
        pending=pending_result.scalar() or 0,
        in_progress=in_progress_result.scalar() or 0,
        done_today=done_today_result.scalar() or 0,
        done_total=done_total_result.scalar() or 0,
        avg_cost_usd=avg_cost_result.scalar(),
    )
