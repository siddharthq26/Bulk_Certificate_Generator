"""
Celery application configuration.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "bulk_cert",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Explicitly import tasks so Celery registers them
import app.tasks.generation_tasks  # noqa: F401


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result expiry (24 hours)
    result_expires=86400,
    # Track task started state
    task_track_started=True,
    # Worker prefetch
    worker_prefetch_multiplier=1,
)
