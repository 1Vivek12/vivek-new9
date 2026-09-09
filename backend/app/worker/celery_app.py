"""Celery application instance and configuration."""

from celery import Celery

from app.core.config import settings
from app.core.logging import logger

celery_app = Celery(
    "news9_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="worker.health_check")
def worker_health_check() -> dict:
    """Basic worker responsiveness probe."""
    logger.info("Worker health ping executed")
    return {"status": "HEALTHY", "worker": "news9_worker"}
