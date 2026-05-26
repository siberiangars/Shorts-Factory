"""Celery worker signals for graceful shutdown and metrics."""
import structlog
from celery.signals import worker_shutdown, worker_ready, task_postrun, task_failure

log = structlog.get_logger()


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    log.info("celery_worker_ready", hostname=sender.hostname)


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """
    Celery already waits for running tasks before shutdown on SIGTERM.
    This hook just logs the event so operators can confirm graceful exit.
    """
    log.info("celery_worker_graceful_shutdown", hostname=getattr(sender, "hostname", "unknown"))


@task_postrun.connect
def on_task_postrun(sender, task_id, task, args, kwargs, retval, state, **_):
    from pipeline.metrics import videos_completed
    if state == "SUCCESS" and task.name == "workers.tasks.process_topic":
        videos_completed.inc()


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **_):
    from pipeline.metrics import videos_failed
    if sender.name == "workers.tasks.process_topic":
        videos_failed.inc()
    log.error(
        "celery_task_failed",
        task=sender.name,
        task_id=task_id,
        error=str(exception),
    )
