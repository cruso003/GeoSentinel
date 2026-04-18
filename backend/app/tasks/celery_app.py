"""Celery application for GeoSentinel background jobs (Spec §5.4).

Phase 2.2: queues split so ML work (InSAR, heavy inference) can't starve
periodic maintenance. Timeouts + retries are declared globally so a stuck
DB or model load surfaces as a retryable failure rather than a hung worker.
"""

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
        "app.tasks.escalation",
        "app.tasks.drift",
        "app.tasks.retrain",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Hard ceiling on any task. Individual tasks override via @task(time_limit=).
    task_time_limit=20 * 60,
    task_soft_time_limit=15 * 60,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        # ML + InSAR are CPU-hungry — route to a dedicated worker pool.
        "app.tasks.ai_inference.*": {"queue": "ml"},
        "app.tasks.insar_processing.*": {"queue": "ml"},
        # Everything else on the default queue.
        "app.tasks.report_generation.*": {"queue": "default"},
        "app.tasks.escalation.*": {"queue": "default"},
        "app.tasks.drift.*": {"queue": "default"},
        # Retrain routes to the ml queue because the (opt-in) body runs TF.
        "app.tasks.retrain.*": {"queue": "ml"},
    },
    beat_schedule={
        "enviroguard-15min": {
            "task": "app.tasks.ai_inference.run_enviroguard_all_sites",
            "schedule": 15 * 60,
            "options": {"queue": "ml", "expires": 12 * 60},
        },
        "slopewatch-5min": {
            "task": "app.tasks.ai_inference.run_slopewatch_all_sites",
            "schedule": 5 * 60,
            "options": {"queue": "ml", "expires": 4 * 60},
        },
        "insar-weekly": {
            "task": "app.tasks.insar_processing.process_sentinel1_scene",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
            "options": {"queue": "ml"},
        },
        "escalation-sweep-1min": {
            "task": "app.tasks.escalation.sweep_unacknowledged",
            "schedule": 60,
            "options": {"queue": "default", "expires": 50},
        },
        "model-drift-daily": {
            "task": "app.tasks.drift.sweep_model_drift",
            "schedule": crontab(hour=2, minute=30),
            "options": {"queue": "default", "expires": 60 * 60},
        },
        # Weekly retrain — no-op until enable_retrain_loop=True. Cadence is
        # Sunday 04:00 UTC so it lands after the InSAR sweep finishes.
        "retrain-weekly": {
            "task": "app.tasks.retrain.sweep_retrain",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
            "options": {"queue": "ml", "expires": 2 * 60 * 60},
        },
    },
)
