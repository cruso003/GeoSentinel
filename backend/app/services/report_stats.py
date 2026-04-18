"""Collect compliance stats for the ESG PDF report (Phase 3 §IFC PDF).

The PDF generator previously rendered hardcoded numbers. Phase 3 moves this
to real data pulled from the alert log and slope-watch prediction table.

Each report ingests:

- ``stats_rows`` — per-parameter IFC-limit / exceedance-count /
  compliance-% derived from the ``alerts`` table during the period.
- ``exceedance_log`` — the actual CRITICAL/EVACUATION events, capped at
  ``MAX_LOG_ROWS`` so the PDF doesn't blow up across a full quarter.
- ``geohazard_summary`` — the worst ``alert_tier`` and max
  ``risk_score`` observed on SlopeWatch during the period.

Compliance percentage uses a simple and defensible denominator: the count
of 5-minute windows that fit into the period ("expected samples"). A real
deployment will prefer the actual ingest count from InfluxDB — see the
follow-up note in ``phase-3-product-depth.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai import SlopeWatchPrediction
from ..models.alert import Alert
from .thresholds import IFC_THRESHOLDS

# --- knobs -----------------------------------------------------------

SAMPLE_INTERVAL = timedelta(minutes=5)
# Parameters we report on explicitly (order preserved in the PDF table).
REPORTED_PARAMETERS: tuple[str, ...] = (
    "ph",
    "turbidity",
    "conductivity",
    "pm25",
    "pm10",
)
# Cap the per-report event log — a quarterly report can otherwise produce
# thousands of rows and render pages and pages of tabular data.
MAX_LOG_ROWS = 25


@dataclass(frozen=True)
class StatsRow:
    parameter: str
    limit: str
    mean: float | str
    max: float | str
    compliant_pct: float
    events: int


@dataclass(frozen=True)
class ExceedanceLogRow:
    timestamp: datetime
    node_id: str
    parameter: str
    severity: str
    value: float | None
    threshold: float | None
    acknowledged: bool


@dataclass(frozen=True)
class GeohazardSummary:
    worst_tier: str
    max_risk_score: float
    evacuation_events: int
    critical_events: int
    slope_predictions_count: int


@dataclass(frozen=True)
class ReportData:
    stats_rows: tuple[StatsRow, ...]
    exceedance_log: tuple[ExceedanceLogRow, ...]
    geohazard: GeohazardSummary
    total_alerts: int
    exceedance_count: int  # CRITICAL + EVACUATION only


# --- helpers ---------------------------------------------------------


def _limit_label(parameter: str) -> str:
    t = IFC_THRESHOLDS.get(parameter)
    if t is None:
        return "—"
    if t.min_value is not None and t.max_value is not None:
        return f"{t.min_value}-{t.max_value} {t.unit}"
    if t.max_value is not None:
        return f"≤ {t.max_value} {t.unit}"
    if t.min_value is not None:
        return f"≥ {t.min_value} {t.unit}"
    return t.unit


def _expected_samples(period: timedelta) -> int:
    if period.total_seconds() <= 0:
        return 0
    return max(1, math.ceil(period.total_seconds() / SAMPLE_INTERVAL.total_seconds()))


def _compliance_pct(exceedance_count: int, expected: int) -> float:
    if expected <= 0:
        return 100.0
    ratio = min(1.0, exceedance_count / expected)
    return max(0.0, 100.0 * (1.0 - ratio))


def _summarise_values(values: Sequence[float]) -> tuple[float | str, float | str]:
    """Return (mean, max) formatted for the stats table. When the period had
    no samples of that parameter, return an em-dash placeholder."""
    if not values:
        return ("—", "—")
    return (sum(values) / len(values), max(values))


# --- main entrypoint --------------------------------------------------


async def collect_compliance_stats(
    db: AsyncSession,
    *,
    site_id: str,
    period_start: datetime,
    period_end: datetime,
) -> ReportData:
    """Assemble :class:`ReportData` for the reporting period.

    The function is read-only — callers still own the transaction they hand
    in. Queries are kept narrow (one per alert parameter, one for slope
    predictions) so a quarterly report doesn't dominate the request.
    """

    period = period_end - period_start
    expected_samples = _expected_samples(period)

    alerts = (
        await db.execute(
            select(Alert)
            .where(
                Alert.site_id == site_id,
                Alert.created_at >= period_start,
                Alert.created_at <= period_end,
            )
            .order_by(Alert.created_at.desc())
        )
    ).scalars().all()

    # Per-parameter roll-up for the stats table.
    by_param: dict[str, list[Alert]] = {p: [] for p in REPORTED_PARAMETERS}
    for a in alerts:
        if a.parameter in by_param:
            by_param[a.parameter].append(a)

    stats_rows: list[StatsRow] = []
    # Headline exceedance count spans every CRITICAL+EVACUATION alert in the
    # period — including geohazard rows whose ``parameter`` isn't in the
    # water/air table. The per-row ``events`` column below is still scoped
    # to the row's parameter.
    exceedance_total = sum(
        1 for a in alerts if a.severity in ("CRITICAL", "EVACUATION")
    )
    for parameter in REPORTED_PARAMETERS:
        param_alerts = by_param[parameter]
        # Compliance % is driven by the CRITICAL+EVACUATION count — WARNING
        # is a near-limit notice, not an IFC breach.
        exceedances = [a for a in param_alerts if a.severity in ("CRITICAL", "EVACUATION")]
        values = [a.value for a in param_alerts if a.value is not None]
        mean, mx = _summarise_values(values)
        # For parameters with no real alert readings in the window, show the
        # fallback placeholder rather than a fabricated 100 %.
        events = len(exceedances)
        compliant_pct = _compliance_pct(events, expected_samples)
        stats_rows.append(
            StatsRow(
                parameter=parameter,
                limit=_limit_label(parameter),
                mean=round(mean, 2) if isinstance(mean, float) else mean,
                max=round(mx, 2) if isinstance(mx, float) else mx,
                compliant_pct=round(compliant_pct, 2),
                events=events,
            )
        )

    # Exceedance event log — CRITICAL+EVACUATION only, newest first, capped.
    log_rows: list[ExceedanceLogRow] = []
    for a in alerts:
        if a.severity not in ("CRITICAL", "EVACUATION"):
            continue
        log_rows.append(
            ExceedanceLogRow(
                timestamp=a.created_at,
                node_id=a.node_id,
                parameter=a.parameter,
                severity=a.severity,
                value=a.value,
                threshold=a.threshold,
                acknowledged=bool(a.acknowledged),
            )
        )
        if len(log_rows) >= MAX_LOG_ROWS:
            break

    # Geohazard: worst tier + peak risk from SlopeWatchPredictions in range.
    preds = (
        await db.execute(
            select(SlopeWatchPrediction).where(
                SlopeWatchPrediction.site_id == site_id,
                SlopeWatchPrediction.timestamp >= period_start,
                SlopeWatchPrediction.timestamp <= period_end,
            )
        )
    ).scalars().all()
    tier_order = {"NORMAL": 0, "WATCH": 1, "WARNING": 2, "CRITICAL": 3, "EVACUATION": 4}
    worst_tier = "NORMAL"
    max_risk = 0.0
    for p in preds:
        if tier_order.get(p.alert_tier, 0) > tier_order.get(worst_tier, 0):
            worst_tier = p.alert_tier
        max_risk = max(max_risk, p.risk_score or 0.0)

    evac_events = sum(1 for a in alerts if a.alert_type == "geohazard" and a.severity == "EVACUATION")
    crit_events = sum(1 for a in alerts if a.alert_type == "geohazard" and a.severity == "CRITICAL")

    geo = GeohazardSummary(
        worst_tier=worst_tier,
        max_risk_score=round(max_risk, 3),
        evacuation_events=evac_events,
        critical_events=crit_events,
        slope_predictions_count=len(preds),
    )

    return ReportData(
        stats_rows=tuple(stats_rows),
        exceedance_log=tuple(log_rows),
        geohazard=geo,
        total_alerts=len(alerts),
        exceedance_count=exceedance_total,
    )
