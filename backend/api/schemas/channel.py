from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.channel import AvatarMode


class VoiceSettings(BaseModel):
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


class ChannelCreate(BaseModel):
    name: str = Field(..., max_length=255)
    niche: str = Field(..., max_length=255)
    language: str = Field(default="ru", max_length=10)

    # B-roll mode
    voice_id: str = Field(default="", max_length=255)
    voice_settings_json: dict = Field(default_factory=lambda: VoiceSettings().model_dump())

    # HeyGen mode
    avatar_mode: AvatarMode = AvatarMode.broll
    heygen_avatar_id: str | None = None
    heygen_voice_id: str | None = None
    heygen_background: str = Field(default="#f8f5f0", max_length=20)
    persona_description: str | None = None

    google_cloud_project_id: str | None = None
    default_tags: list[str] = Field(default_factory=list)
    description_template: str | None = None
    script_prompt_template: str | None = None
    auto_publish_public: bool = False
    auto_post_instagram: bool = False


class ChannelUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    niche: str | None = Field(None, max_length=255)
    language: str | None = Field(None, max_length=10)
    voice_id: str | None = Field(None, max_length=255)
    voice_settings_json: dict | None = None
    avatar_mode: AvatarMode | None = None
    heygen_avatar_id: str | None = None
    heygen_voice_id: str | None = None
    heygen_background: str | None = None
    persona_description: str | None = None
    google_cloud_project_id: str | None = None
    default_tags: list[str] | None = None
    description_template: str | None = None
    script_prompt_template: str | None = None
    auto_publish_public: bool | None = None
    auto_post_instagram: bool | None = None


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    niche: str
    language: str
    voice_id: str
    voice_settings_json: dict
    avatar_mode: AvatarMode
    heygen_avatar_id: str | None
    heygen_voice_id: str | None
    heygen_background: str
    persona_description: str | None
    google_cloud_project_id: str | None
    youtube_channel_id: str | None
    instagram_user_id: str | None
    default_tags: list
    description_template: str | None
    script_prompt_template: str | None
    auto_publish_public: bool
    auto_post_instagram: bool
    daily_upload_count: int
    daily_upload_count_reset_at: datetime | None
    token_expires_at: datetime | None
    has_oauth: bool = False
    has_instagram: bool = False
    created_at: datetime
    updated_at: datetime
