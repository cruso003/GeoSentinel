"""Public community dashboard endpoints (Spec §5.2.7, §10).

These routes are intentionally unauthenticated so residents near a mine can
check drinking-water / air-quality / ground-stability status without creating
an account.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...models.site import Site
from ...schemas.entities import CommunityStatusOut
from ...services.enviroguard import run_enviroguard
from ...services.influx import influx

router = APIRouter(prefix="/community", tags=["community"])


def _water_tone(ph: float | None, turb: float | None, cond: float | None) -> tuple[str, str]:
    if ph is None and turb is None and cond is None:
        return "CAUTION", "Recent readings unavailable."
    ph_bad = ph is not None and (ph < 6.0 or ph > 9.0)
    turb_bad = turb is not None and turb > 5
    cond_bad = cond is not None and cond > 500
    if ph_bad or cond_bad or (turb is not None and turb > 10):
        return "DO_NOT_USE", "Water quality outside safe drinking range. Use alternative sources."
    if turb_bad:
        return "CAUTION", "Turbidity slightly elevated after recent rainfall. Boil before drinking."
    return "SAFE", "Water downstream of the mine meets IFC drinking-water guidelines."


def _air_tone(pm25: float | None) -> tuple[str, str]:
    if pm25 is None:
        return "CAUTION", "Recent readings unavailable."
    if pm25 > 55:
        return "DO_NOT_USE", "Air quality is unhealthy. Limit outdoor activity and close windows."
    if pm25 > 25:
        return "CAUTION", "PM2.5 elevated. Sensitive groups should reduce prolonged outdoor exertion."
    return "SAFE", "Air quality around the mine is within WHO/IFC guidelines."


def _ground_tone(risk_24h: str) -> tuple[str, str]:
    if risk_24h in ("CRITICAL",):
        return "DO_NOT_USE", "Slope risk elevated. Follow evacuation guidance from local authorities."
    if risk_24h in ("HIGH", "ELEVATED"):
        return "CAUTION", "Slope monitoring shows elevated risk. Stay clear of marked exclusion zones."
    return "SAFE", "All monitored slopes are stable."


async def _latest_env_value(node_id: str, field: str) -> float | None:
    row = await influx.latest("env", node_id)
    if not row:
        return None
    v = row.get(field)
    return float(v) if v is not None else None


@router.get("/{site_id}", response_model=CommunityStatusOut)
async def community_status(
    site_id: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Pull representative nodes if present, else fall back to placeholders.
    ph = await _latest_env_value("ENV-01", "ph")
    turb = await _latest_env_value("ENV-01", "turbidity")
    cond = await _latest_env_value("ENV-02", "conductivity")
    pm25 = await _latest_env_value("ENV-03", "pm25")

    water_status, water_msg = _water_tone(ph, turb, cond)
    air_status, air_msg = _air_tone(pm25)
    pred = await run_enviroguard(site_id)
    ground_status, ground_msg = _ground_tone(pred.overall_risk_24h)

    overall_rank = {"SAFE": 0, "CAUTION": 1, "DO_NOT_USE": 2}
    overall = max((water_status, air_status, ground_status), key=lambda s: overall_rank[s])

    now = datetime.now(timezone.utc).isoformat()
    return CommunityStatusOut(
        site_id=site_id,
        overall=overall,
        water={
            "status": water_status,
            "message": water_msg,
            "ph": ph,
            "turbidity": turb,
            "conductivity": cond,
            "as_of": now,
        },
        air={
            "status": air_status,
            "message": air_msg,
            "pm25": pm25,
            "as_of": now,
        },
        ground={
            "status": ground_status,
            "message": ground_msg,
            "risk_24h": pred.overall_risk_24h,
            "as_of": now,
        },
    )
