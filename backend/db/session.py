from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings

_settings = get_settings()

# ── Async engine (FastAPI) ────────────────────────────────────────────────────
# psycopg3 (postgresql+psycopg) supports create_async_engine natively.
async_engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
)

# ── Sync engine (Celery workers) ──────────────────────────────────────────────
# Same psycopg3 URL works with create_engine for synchronous access.
sync_engine = create_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

sync_session_factory: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    autoflush=False,
)
