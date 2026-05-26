import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.channel import Channel
    from models.video import Video


class TopicStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class Topic(BaseModel):
    __tablename__ = "topics"

    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    brief: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TopicStatus] = mapped_column(
        SAEnum(TopicStatus, name="topicstatus"),
        nullable=False,
        default=TopicStatus.pending,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scheduled_at: Mapped[datetime | None] = mapped_column(index=True)
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    channel: Mapped["Channel"] = relationship("Channel", back_populates="topics")
    video: Mapped["Video | None"] = relationship("Video", back_populates="topic", uselist=False)
