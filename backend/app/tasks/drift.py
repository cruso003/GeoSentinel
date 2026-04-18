"""Daily drift sweep (Phase 2.4 §3).

Compares the last 24 h of predictions against a 7-day reference window for
every deployed model, updates the ``gs_model_psi{model,feature}`` gauge,
and observes each confidence into ``gs_model_confidence``. We compute PSI
on the model *outputs* (risk probabilities) rather than inputs because
inputs live in InfluxDB and are site-partitioned — probability drift is
the earliest signal that the learned mapping has gone stale.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..core.db import SessionLocal
from ..models.ai import EnviroGuardPrediction, SlopeWatchPrediction
from ..services import drift, metrics
from .celery_app import celery_app

# 24 h current window vs 7-day reference (excluding the current window) —
# a week is short enough to stay relevant after a site reconfiguration but
# long enough to have signal outside a single diurnal cycle.
_CURRENT_WINDOW = timedelta(hours=24)
_REFERENCE_WINDOW = timedelta(days=7)


_ENVIROGUARD_FEATURES = (
    "ph_exceedance_24h",
    "turbidity_exceedance_24h",
    "do_exceedance_24h",
    "conductivity_exceedance_24h",
    "pm25_exceedance_24h",
    "ph_exceedance_72h",
    "turbidity_exceedance_72h",
)

_SLOPEWATCH_FEATURES = (
    "risk_score",
    "pore_pressure_factor",
    "tilt_factor",
    "insar_factor",
    "rainfall_factor",
)


async def _collect(db, model_cls, features, cutoff_start, cutoff_end):
    stmt = select(model_cls).where(
        model_cls.timestamp >= cutoff_start, model_cls.timestamp < cutoff_end
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {f: [float(getattr(r, f)) for r in rows] for f in features}


def _publish(model_name: str, report: dict[str, float]) -> None:
    for feature, value in report.items():
        metrics.model_psi.set(value, model=model_name, feature=feature)


async def _run_once(now: datetime | None = None) -> dict[str, dict[str, float]]:
    now = now or datetime.now(UTC)
    current_start = now - _CURRENT_WINDOW
    reference_start = now - _REFERENCE_WINDOW
    summary: dict[str, dict[str, float]] = {}

    async with SessionLocal() as db:
        for name, model_cls, features, confidence_attr in (
            (
                "enviroguard",
                EnviroGuardPrediction,
                _ENVIROGUARD_FEATURES,
                "confidence",
            ),
            ("slopewatch", SlopeWatchPrediction, _SLOPEWATCH_FEATURES, "risk_score"),
        ):
            reference = await _collect(
                db, model_cls, features, reference_start, current_start
            )
            current = await _collect(
                db, model_cls, features, current_start, now
            )
            report = drift.psi_report(reference, current)
            _publish(name, report)
            summary[name] = report

            # Confidence histogram tracks the actual output distribution so
            # an operator can eyeball "the model used to be decisive, now
            # everything is 0.5" without waiting on PSI alarms.
            current_conf = await _collect(
                db, model_cls, (confidence_attr,), current_start, now
            )
            for v in current_conf.get(confidence_attr, ()):
                metrics.model_confidence.observe(v, model=name)

    return summary


@celery_app.task(
    name="app.tasks.drift.sweep_model_drift",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    time_limit=300,
)
def sweep_model_drift() -> dict:
    report = asyncio.run(_run_once())
    return {
        model: {k: round(v, 4) for k, v in feats.items()}
        for model, feats in report.items()
    }
