import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.generation_log import GenerationLog
    from models.topic import Topic


class VideoStatus(str, enum.Enum):
    pending = "pending"
    generating_script = "generating_script"
    generating_voice = "generating_voice"
    fetching_broll = "fetching_broll"
    transcribing = "transcribing"
    assembling = "assembling"
    uploading = "uploading"
    done = "done"
    failed = "failed"


class Video(BaseModel):
    __tablename__ = "videos"

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"), nullable=False, unique=True, index=True
    )
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False, index=True)

    script_text: Mapped[str | None] = mapped_column(Text)
    script_title: Mapped[str | None] = mapped_column(String(512))
    script_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    script_description: Mapped[str | None] = mapped_column(Text)

    broll_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    broll_video_hashes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    voice_audio_path: Mapped[str | None] = mapped_column(Text)
    broll_dir: Mapped[str | None] = mapped_column(Text)
    subtitles_path: Mapped[str | None] = mapped_column(Text)
    final_video_path: Mapped[str | None] = mapped_column(Text)

    duration_sec: Mapped[float | None] = mapped_column()
    youtube_video_id: Mapped[str | None] = mapped_column(String(255), index=True)
    youtube_url: Mapped[str | None] = mapped_column(Text)

    status: Mapped[VideoStatus] = mapped_column(
        SAEnum(VideoStatus, name="videostatus"),
        nullable=False,
        default=VideoStatus.pending,
        index=True,
    )
    generation_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column()

    # Instagram
    instagram_media_id: Mapped[str | None] = mapped_column(String(255))
    instagram_url: Mapped[str | None] = mapped_column(Text)
    instagram_published_at: Mapped[datetime | None] = mapped_column()

    topic: Mapped["Topic"] = relationship("Topic", back_populates="video")
    logs: Mapped[list["GenerationLog"]] = relationship(
        "GenerationLog", back_populates="video", order_by="GenerationLog.id"
    )
