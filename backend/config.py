from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://shorts:shorts@postgres:5432/shorts"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Encryption
    fernet_key: str

    # AI services
    anthropic_api_key: str
    elevenlabs_api_key: str
    pexels_api_key: str
    heygen_api_key: str = "placeholder-add-later"
    pixabay_api_key: str = "placeholder-add-later"  # free at pixabay.com/api/docs/
    groq_api_key: str = "placeholder-add-later"     # free at console.groq.com
    fal_api_key: str = "placeholder-add-later"      # fal.ai — Seedance 2.0 video gen
    piapi_api_key: str = "placeholder-add-later"   # piapi.ai — FLUX + Kling video gen (отключён)

    # Storyblocks API — developer.storyblocks.com (5 бесплатных загрузок при регистрации)
    storyblocks_public_key: str = "placeholder-add-later"
    storyblocks_private_key: str = "placeholder-add-later"
    storyblocks_project_id: str = "placeholder-add-later"

    # YouTube OAuth
    youtube_client_secrets_file: str = "/app/secrets/client_secret.json"
    youtube_oauth_redirect_uri: str = "http://localhost:8000/api/channels/oauth-callback"

    # Storage
    storage_path: str = "/app/storage"

    # Auth
    api_auth_token: str = "changeme"

    # Limits
    daily_upload_quota_per_project: int = 6
    default_video_fps: int = 30
    default_video_resolution: str = "1080x1920"

    # Frontend
    next_public_api_url: str = "http://localhost:8000"

    # Instagram / Meta
    meta_app_id: str = ""
    meta_app_secret: str = ""
    instagram_oauth_redirect_uri: str = "http://185.252.215.53:8000/api/instagram/oauth-callback"
    # Public base URL used to build video URLs for Instagram
    storage_base_url: str = "http://185.252.215.53:8000"

    # Лицензии — список admin-email через запятую
    allowed_emails: str = ""

    # Optional: Sentry
    sentry_dsn: str = ""

    @property
    def video_width(self) -> int:
        return int(self.default_video_resolution.split("x")[0])

    @property
    def video_height(self) -> int:
        return int(self.default_video_resolution.split("x")[1])


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
