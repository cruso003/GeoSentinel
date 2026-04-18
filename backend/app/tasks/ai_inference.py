"""Scheduled AI inference (EnviroGuard 15m, SlopeWatch 5m) — Spec §13.

Each run:
  1. Pulls site (+ slope) list from Postgres.
  2. Runs the inference service (TFLite-backed in Phase 2, synthetic fallback).
  3. Persists the prediction row.
  4. Feeds the alert engine so predictive alerts fire automatically.
  5. Broadcasts `AI_PREDICTION` over the WebSocket hub.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from sqlalchemy import select

from ..core.db import SessionLocal
from ..models.ai import EnviroGuardPrediction, SlopeWatchPrediction
from ..models.site import MineSlope, Site
from ..services.alert_engine import evaluate_enviroguard, evaluate_slopewatch
from ..services.enviroguard import run_enviroguard
from ..services.slopewatch import run_slopewatch
from ..services.ws_hub import hub
from .celery_app import celery_app

log = logging.getLogger(__name__)


async def _enviroguard_all() -> int:
    async with SessionLocal() as db:
        site_ids = (await db.execute(select(Site.id))).scalars().all()
        n = 0
        for sid in site_ids:
            pred = await run_enviroguard(sid)
            db.add(EnviroGuardPrediction(
                id=str(uuid4()),
                site_id=pred.site_id,
                timestamp=pred.timestamp,
                ph_exceedance_24h=pred.ph_exceedance_24h,
                turbidity_exceedance_24h=pred.turbidity_exceedance_24h,
                do_exceedance_24h=pred.do_exceedance_24h,
                conductivity_exceedance_24h=pred.conductivity_exceedance_24h,
                pm25_exceedance_24h=pred.pm25_exceedance_24h,
                ph_exceedance_72h=pred.ph_exceedance_72h,
                turbidity_exceedance_72h=pred.turbidity_exceedance_72h,
                overall_risk_24h=pred.overall_risk_24h,
                overall_risk_72h=pred.overall_risk_72h,
                confidence=pred.confidence,
            ))
            await evaluate_enviroguard(db, pred)
            await hub.broadcast(
                sid,
                {"type": "AI_PREDICTION", "model": "enviroguard",
                 "payload": pred.model_dump(mode="json")},
            )
            n += 1
        await db.commit()
        return n


async def _slopewatch_all() -> int:
    async with SessionLocal() as db:
        rows = (await db.execute(select(MineSlope.site_id, MineSlope.id))).all()
        grouped: dict[str, list[str]] = {}
        for site_id, slope_id in rows:
            grouped.setdefault(site_id, []).append(slope_id)
        n = 0
        for sid, slope_ids in grouped.items():
            preds = await run_slopewatch(sid, slope_ids)
            for p in preds:
                db.add(SlopeWatchPrediction(
                    id=str(uuid4()),
                    site_id=p.site_id,
                    slope_id=p.slope_id,
                    timestamp=p.timestamp,
                    risk_score=p.risk_score,
                    alert_tier=p.alert_tier,
                    pore_pressure_factor=p.pore_pressure_factor,
                    tilt_factor=p.tilt_factor,
                    insar_factor=p.insar_factor,
                    rainfall_factor=p.rainfall_factor,
                    trend=p.trend,
                    trend_rate=p.trend_rate,
                ))
                await hub.broadcast(
                    sid,
                    {"type": "AI_PREDICTION", "model": "slopewatch",
                     "payload": p.model_dump(mode="json")},
                )
                n += 1
            await evaluate_slopewatch(db, preds)
        await db.commit()
        return n


@celery_app.task(
    name="app.tasks.ai_inference.run_enviroguard_all_sites",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    time_limit=10 * 60,
    soft_time_limit=8 * 60,
)
def run_enviroguard_all_sites() -> int:
    return asyncio.run(_enviroguard_all())


@celery_app.task(
    name="app.tasks.ai_inference.run_slopewatch_all_sites",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    time_limit=5 * 60,
    soft_time_limit=4 * 60,
)
def run_slopewatch_all_sites() -> int:
    return asyncio.run(_slopewatch_all())
