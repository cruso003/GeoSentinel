"""Scheduled AI inference (EnviroGuard 15m, SlopeWatch 5m) — Spec §13."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ..core.db import SessionLocal
from ..models.site import MineSlope, Site
from ..services.enviroguard import run_enviroguard
from ..services.slopewatch import run_slopewatch
from ..services.ws_hub import hub
from .celery_app import celery_app

log = logging.getLogger(__name__)


async def _enviroguard_all() -> int:
    async with SessionLocal() as db:
        site_ids = (await db.execute(select(Site.id))).scalars().all()
    for sid in site_ids:
        pred = await run_enviroguard(sid)
        await hub.broadcast(
            sid,
            {"type": "AI_PREDICTION", "model": "enviroguard", "payload": pred.model_dump(mode="json")},
        )
    return len(site_ids)


async def _slopewatch_all() -> int:
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(MineSlope.site_id, MineSlope.id))
        ).all()
    grouped: dict[str, list[str]] = {}
    for site_id, slope_id in rows:
        grouped.setdefault(site_id, []).append(slope_id)
    n = 0
    for sid, slope_ids in grouped.items():
        preds = await run_slopewatch(sid, slope_ids)
        for p in preds:
            await hub.broadcast(
                sid,
                {"type": "AI_PREDICTION", "model": "slopewatch", "payload": p.model_dump(mode="json")},
            )
            n += 1
    return n


@celery_app.task(name="app.tasks.ai_inference.run_enviroguard_all_sites")
def run_enviroguard_all_sites() -> int:
    return asyncio.run(_enviroguard_all())


@celery_app.task(name="app.tasks.ai_inference.run_slopewatch_all_sites")
def run_slopewatch_all_sites() -> int:
    return asyncio.run(_slopewatch_all())
