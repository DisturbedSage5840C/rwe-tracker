"""Celery app configuration for distributed background processing."""

from __future__ import annotations

from celery import Celery
from kombu import Queue

from apps.api.config import get_settings
from apps.common.logging import configure_logging

configure_logging()
settings = get_settings()

celery_app = Celery(
    "rwe_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "apps.worker.tasks.analysis",
        "apps.worker.tasks.ingestion",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="analysis",
    task_queues=(
        Queue("analysis"),
        Queue("ingestion"),
        Queue("celery"),
    ),
    task_routes={
        "analysis.*": {"queue": "analysis"},
        "ingestion.*": {"queue": "ingestion"},
        "celery.chord_unlock": {"queue": "analysis"},
    },
)
