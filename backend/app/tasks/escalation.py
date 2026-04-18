"""Periodic escalation sweeper (Phase 2.3 §5).

Runs once a minute; advances one hop per unacked CRITICAL alert at a time so
a storm of alerts does not wake the entire ladder simultaneously.
"""

from __future__ import annotations

import asyncio
import logging

from ..core.db import SessionLocal
from ..services.escalation import sweep_unacknowledged
from .celery_app import celery_app

log = logging.getLogger(__name__)


async def _sweep_once() -> int:
    async with SessionLocal() as db:
        return await sweep_unacknowledged(db)


@celery_app.task(
    name="app.tasks.escalation.sweep_unacknowledged",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    time_limit=60,
    soft_time_limit=45,
)
def sweep_unacknowledged_task() -> int:
    n = asyncio.run(_sweep_once())
    if n:
        log.info("escalation.sweep dispatched=%d", n)
    return n
