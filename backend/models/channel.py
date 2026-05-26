import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.topic import Topic


class AvatarMode(str, enum.Enum):
    broll = "broll"        # B-roll + ElevenLabs voice + FFmpeg
    heygen = "heygen"      # HeyGen talking avatar


class Channel(BaseModel):
    __tablename__ = "channels"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ru")

    # ── B-roll mode ───────────────────────────────────────────────────────────
    voice_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    voice_settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # ── HeyGen avatar mode ────────────────────────────────────────────────────
    avatar_mode: Mapped[AvatarMode] = mapped_column(
        SAEnum(AvatarMode, name="avatarmode"),
        nullable=False,
        default=AvatarMode.broll,
    )
    heygen_avatar_id: Mapped[str | None] = mapped_column(String(255))
    heygen_voice_id: Mapped[str | None] = mapped_column(String(255))
    # Background color for HeyGen frame (hex, e.g. "#f8f5f0")
    heygen_background: Mapped[str] = mapped_column(String(20), nullable=False, default="#f8f5f0")
    # Character persona description injected into the script prompt
    persona_description: Mapped[str | None] = mapped_column(Text)

    # ── YouTube / Auth ────────────────────────────────────────────────────────
    google_cloud_project_id: Mapped[str | None] = mapped_column(String(255))
    youtube_channel_id: Mapped[str | None] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column()

    # ── Content defaults ──────────────────────────────────────────────────────
    default_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description_template: Mapped[str | None] = mapped_column(Text)
    script_prompt_template: Mapped[str | None] = mapped_column(Text)

    auto_publish_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_upload_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_upload_count_reset_at: Mapped[datetime | None] = mapped_column()

    # ── Instagram ─────────────────────────────────────────────────────────────
    instagram_user_id: Mapped[str | None] = mapped_column(String(255))
    instagram_access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    # Auto-post to Instagram after YouTube upload
    auto_post_instagram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    topics: Mapped[list["Topic"]] = relationship("Topic", back_populates="channel")
