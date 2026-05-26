from celery import Celery
import workers.signals  # noqa: F401 — registers signal handlers
from celery.schedules import crontab

from config import get_settings

settings = get_settings()

celery_app = Celery(
    "shorts_factory",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # ack only after task completes (safe retry on crash)
    worker_prefetch_multiplier=1, # one task at a time per worker slot (pipeline tasks are heavy)
    task_routes={
        "workers.tasks.process_topic": {"queue": "pipeline"},
        "workers.tasks.check_scheduled_topics": {"queue": "scheduler"},
        "workers.tasks.reset_daily_quotas": {"queue": "scheduler"},
    },
    beat_schedule={
        "check-scheduled-every-5-min": {
            "task": "workers.tasks.check_scheduled_topics",
            "schedule": 300.0,
        },
        "reset-daily-quotas-utc-midnight": {
            "task": "workers.tasks.reset_daily_quotas",
            "schedule": crontab(hour=0, minute=0),
        },
    },
)
