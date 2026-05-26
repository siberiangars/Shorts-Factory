import os
import pytest
from unittest.mock import patch

# Set env vars before any imports that read them
os.environ.setdefault("FERNET_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-key")
os.environ.setdefault("PEXELS_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://shorts:shorts@localhost:5432/shorts_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("STORAGE_PATH", "/tmp/shorts_test_storage")
os.environ.setdefault("YOUTUBE_CLIENT_SECRETS_FILE", "/tmp/client_secret.json")
os.environ.setdefault("API_AUTH_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def reset_settings_cache():
    from config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
