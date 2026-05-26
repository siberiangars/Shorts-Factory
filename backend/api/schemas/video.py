from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.video import VideoStatus


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    channel_id: int
    topic_title: str | None = None   # injected from topic join
    script_title: str | None
    script_tags: list
    script_description: str | None
    broll_keywords: list
    duration_sec: float | None
    youtube_video_id: str | None
    youtube_url: str | None
    status: VideoStatus
    generation_cost_usd: Decimal | None
    error_message: str | None
    published_at: datetime | None
    instagram_media_id: str | None = None
    instagram_url: str | None = None
    created_at: datetime
    updated_at: datetime


class VideoDetail(VideoRead):
    script_text: str | None
    voice_audio_path: str | None
    final_video_path: str | None
    broll_video_hashes: list
