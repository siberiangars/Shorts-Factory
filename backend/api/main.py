import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from config import get_settings

# ── Structlog configuration ───────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


def _configure_sentry(settings) -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment="production",
        )
        log.info("sentry_initialized")
    except ImportError:
        log.warning("sentry_sdk_not_installed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_sentry(settings)
    log.info("shorts_factory_starting", storage_path=settings.storage_path)
    yield
    log.info("shorts_factory_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Shorts Factory API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://185.252.215.53:3000",
            "http://185.252.215.53",
            "http://localhost:3000",
            "http://localhost:8000",
            settings.next_public_api_url,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus scrape endpoint (no auth — assumed internal network only)
    app.mount("/metrics", make_asgi_app())

    from api.routes import channels, heygen, instagram, licenses, stats, topics, videos
    app.include_router(channels.router,  prefix="/api/channels",  tags=["channels"])
    app.include_router(topics.router,    prefix="/api/topics",    tags=["topics"])
    app.include_router(videos.router,    prefix="/api/videos",    tags=["videos"])
    app.include_router(stats.router,     prefix="/api/stats",     tags=["stats"])
    app.include_router(heygen.router,    prefix="/api/heygen",    tags=["heygen"])
    app.include_router(instagram.router, prefix="/api/instagram", tags=["instagram"])
    app.include_router(licenses.router,  prefix="/api/licenses",  tags=["licenses"])

    return app


app = create_app()


@app.get("/health", status_code=status.HTTP_200_OK, tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
