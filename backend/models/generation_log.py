import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.video import Video


class LogStatus(str, enum.Enum):
    start = "start"
    success = "success"
    failed = "failed"


class GenerationLog(BaseModel):
    __tablename__ = "generation_logs"

    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[LogStatus] = mapped_column(
        SAEnum(LogStatus, name="logstatus"), nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    payload_json: Mapped[dict | None] = mapped_column(JSON)

    video: Mapped["Video"] = relationship("Video", back_populates="logs")
