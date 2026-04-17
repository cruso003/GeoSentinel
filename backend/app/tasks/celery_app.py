"""Celery application for GeoSentinel background jobs (Spec §5.4)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ..core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "geosentinel",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_broker_url,
    include=[
        "app.tasks.ai_inference",
        "app.tasks.report_generation",
        "app.tasks.insar_processing",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "enviroguard-15min": {
            "task": "app.tasks.ai_inference.run_enviroguard_all_sites",
            "schedule": 15 * 60,  # every 15 min
        },
        "slopewatch-5min": {
            "task": "app.tasks.ai_inference.run_slopewatch_all_sites",
            "schedule": 5 * 60,
        },
        "insar-weekly": {
            "task": "app.tasks.insar_processing.process_sentinel1_scene",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00 UTC
        },
    },
)
