"""Daily WATCH/WARNING digest task (Phase 2.3 §Digests).

Beat fires once a day at 07:00 UTC. The service-layer function in
``app.services.digest`` is where the real work lives — this task is a
thin shim that opens a session and forwards the call so the business
logic stays sync-testable without Celery or a broker.
"""

from __future__ import annotations

import asyncio
import logging

from ..core.db import SessionLocal
from ..services.digest import send_digests
from ..services.notifications import notifications
from .celery_app import celery_app

log = logging.getLogger(__name__)


async def _run_once() -> dict:
    async with SessionLocal() as db:
        return await send_digests(db, service=notifications)


@celery_app.task(
    name="app.tasks.digest.send_daily_digest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    time_limit=15 * 60,
    soft_time_limit=12 * 60,
)
def send_daily_digest() -> dict:
    summary = asyncio.run(_run_once())
    log.info("digest.sweep %s", summary)
    return summary
