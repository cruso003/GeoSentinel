"""Alert engine (Spec §7).

Evaluates incoming sensor readings + AI predictions against IFC thresholds and
SlopeWatch tiers, writes `Alert` rows, dedupes within a rolling 60 s window
per `(node_id, parameter, severity)`, and broadcasts `ALERT_NEW` via the
WebSocket hub. Called from:
  - `/sensors/ingest` (threshold alerts)
  - `ai_inference` Celery task (predictive alerts)
  - `mqtt_client` (live telemetry)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.alert import Alert
from ..schemas.ai import EnviroGuardPredictionOut, SlopeWatchPredictionOut
from ..schemas.sensors import EnvSensorReading, GeoSensorReading
from . import metrics
from .notifications import notifications
from .thresholds import IFC_THRESHOLDS, check
from .ws_hub import hub

log = logging.getLogger(__name__)

DEDUP_WINDOW = timedelta(seconds=60)


async def _already_alerting(
    db: AsyncSession,
    site_id: str,
    node_id: str,
    parameter: str,
    severity: str,
) -> bool:
    cutoff = datetime.now(timezone.utc) - DEDUP_WINDOW
    stmt = (
        select(Alert.id)
        .where(
            Alert.site_id == site_id,
            Alert.node_id == node_id,
            Alert.parameter == parameter,
            Alert.severity == severity,
            Alert.created_at >= cutoff,
            Alert.acknowledged.is_(False),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def _emit(
    db: AsyncSession,
    *,
    site_id: str,
    node_id: str,
    alert_type: str,
    severity: str,
    parameter: str,
    value: Optional[float],
    threshold: Optional[float],
    message: str,
) -> Optional[Alert]:
    if await _already_alerting(db, site_id, node_id, parameter, severity):
        return None
    alert = Alert(
        id=str(uuid4()),
        site_id=site_id,
        node_id=node_id,
        alert_type=alert_type,
        severity=severity,
        parameter=parameter,
        value=value,
        threshold=threshold,
        message=message,
    )
    db.add(alert)
    await db.flush()
    await hub.broadcast(
        site_id,
        {
            "type": "ALERT_NEW",
            "alert": {
                "id": alert.id,
                "site_id": alert.site_id,
                "node_id": alert.node_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "parameter": alert.parameter,
                "value": alert.value,
                "threshold": alert.threshold,
                "message": alert.message,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            },
        },
    )
    metrics.alerts_emitted_total.inc(severity=severity, type=alert_type)
    if severity in ("CRITICAL", "EVACUATION"):
        await notifications.dispatch(site_id=site_id, severity=severity, message=message)
    return alert


ENV_FIELDS = (
    "ph", "turbidity", "dissolved_oxygen", "conductivity", "pm25", "pm10",
    "so2", "no2", "noise_db",
)
GEO_FIELDS = ("tilt_x", "tilt_y", "crack_displacement", "pore_pressure")


async def evaluate_env(db: AsyncSession, r: EnvSensorReading) -> list[Alert]:
    out: list[Alert] = []
    for field in ENV_FIELDS:
        value = getattr(r, field, None)
        if value is None:
            continue
        t = IFC_THRESHOLDS.get(field)
        if t is None:
            continue
        c = check(field, value)
        if c.exceeded:
            limit = t.max_value if (t.max_value is not None and value > t.max_value) else t.min_value
            a = await _emit(
                db,
                site_id=r.site_id,
                node_id=r.node_id,
                alert_type="threshold",
                severity=t.severity_on_breach,
                parameter=field,
                value=value,
                threshold=limit,
                message=f"{field} {value:.2f} {t.unit} outside IFC limit "
                        f"[{t.min_value}, {t.max_value}] at {r.node_id}.",
            )
            if a:
                out.append(a)
    return out


async def evaluate_geo(db: AsyncSession, r: GeoSensorReading) -> list[Alert]:
    out: list[Alert] = []
    for field in GEO_FIELDS:
        value = getattr(r, field, None)
        if value is None:
            continue
        t = IFC_THRESHOLDS.get(field)
        if t is None:
            continue
        c = check(field, value)
        if c.exceeded:
            a = await _emit(
                db,
                site_id=r.site_id,
                node_id=r.node_id,
                alert_type="geotechnical_threshold",
                severity=t.severity_on_breach,
                parameter=field,
                value=value,
                threshold=t.max_value if t.max_value is not None else t.min_value,
                message=f"{field} {value:.3f} {t.unit} out of range at {r.node_id}.",
            )
            if a:
                out.append(a)
    if r.seismic_event and r.seismic_magnitude and r.seismic_magnitude >= 3.0:
        a = await _emit(
            db,
            site_id=r.site_id,
            node_id=r.node_id,
            alert_type="seismic",
            severity="CRITICAL",
            parameter="seismic_magnitude",
            value=r.seismic_magnitude,
            threshold=3.0,
            message=f"Seismic event M{r.seismic_magnitude:.1f} detected at {r.node_id}.",
        )
        if a:
            out.append(a)
    return out


async def evaluate_enviroguard(
    db: AsyncSession, pred: EnviroGuardPredictionOut
) -> list[Alert]:
    out: list[Alert] = []
    heads = {
        "ph": pred.ph_exceedance_24h,
        "turbidity": pred.turbidity_exceedance_24h,
        "dissolved_oxygen": pred.do_exceedance_24h,
        "conductivity": pred.conductivity_exceedance_24h,
        "pm25": pred.pm25_exceedance_24h,
    }
    for param, prob in heads.items():
        if prob < 0.6:
            continue
        severity = "CRITICAL" if prob >= 0.85 else "WARNING"
        a = await _emit(
            db,
            site_id=pred.site_id,
            node_id="enviroguard",
            alert_type="predictive",
            severity=severity,
            parameter=param,
            value=prob,
            threshold=0.6,
            message=f"EnviroGuard predicts {prob*100:.0f}% chance of {param} "
                    f"exceedance in next 24 h.",
        )
        if a:
            out.append(a)
    return out


async def evaluate_slopewatch(
    db: AsyncSession, preds: Iterable[SlopeWatchPredictionOut]
) -> list[Alert]:
    tier_to_severity = {
        "WATCH": "INFO",
        "WARNING": "WARNING",
        "CRITICAL": "CRITICAL",
        "EVACUATION": "EVACUATION",
    }
    out: list[Alert] = []
    for p in preds:
        sev = tier_to_severity.get(p.alert_tier)
        if sev is None:
            continue
        a = await _emit(
            db,
            site_id=p.site_id,
            node_id=p.slope_id,
            alert_type="geohazard",
            severity=sev,
            parameter="slope_risk",
            value=p.risk_score,
            threshold=0.45,
            message=f"SlopeWatch tier {p.alert_tier} at {p.slope_id} "
                    f"(risk {p.risk_score:.2f}, trend {p.trend}).",
        )
        if a:
            out.append(a)
    return out
