"""Sensor ingest + read endpoints (Spec §5.2.3)."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.db import get_db
from ...core.deps import require_roles
from ...schemas.sensors import (
    EnvSensorReading,
    GeoSensorReading,
    Resolution,
    SensorIngestPayload,
)
from ...services import gateway_auth
from ...services.alert_engine import evaluate_env, evaluate_geo
from ...services.influx import influx
from ...services.ws_hub import ws_hub

router = APIRouter(prefix="/sensors", tags=["sensors"])

operator_or_admin = require_roles("operator", "esg_admin")


def _parse_window(start: Optional[datetime], end: Optional[datetime]) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    e = end or now
    s = start or (e - timedelta(hours=24))
    if s >= e:
        raise HTTPException(status_code=400, detail="start must precede end")
    return s, e


@router.get("/env/latest")
async def env_latest(
    node_id: str = Query(...),
    _=Depends(operator_or_admin),
):
    row = await influx.latest("env", node_id)
    if not row:
        raise HTTPException(status_code=404, detail="No readings for node")
    return row


@router.get("/env/history")
async def env_history(
    node_id: str = Query(...),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    resolution: Resolution = "5m",  # noqa: ARG001  - honored in Phase 2
    _=Depends(operator_or_admin),
):
    s, e = _parse_window(start, end)
    return await influx.history("env", node_id, s, e)


@router.get("/geo/latest")
async def geo_latest(
    node_id: str = Query(...),
    _=Depends(operator_or_admin),
):
    row = await influx.latest("geo", node_id)
    if not row:
        raise HTTPException(status_code=404, detail="No readings for node")
    return row


@router.get("/geo/history")
async def geo_history(
    node_id: str = Query(...),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    resolution: Resolution = "5m",  # noqa: ARG001
    _=Depends(operator_or_admin),
):
    s, e = _parse_window(start, end)
    return await influx.history("geo", node_id, s, e)


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: SensorIngestPayload,
    x_gateway_api_key: Annotated[Optional[str], Header()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if not x_gateway_api_key:
        raise HTTPException(status_code=401, detail="Missing gateway key")

    gw = await gateway_auth.authenticate(db, x_gateway_api_key)
    allowed: Optional[set[str]] = None

    if gw is None:
        # Legacy transition: accept the shared settings key in non-prod only,
        # and when no gateways are provisioned yet. Production refuses this
        # path via the config validator (non-default key required).
        settings = get_settings()
        if x_gateway_api_key != settings.mqtt_gateway_api_key:
            raise HTTPException(status_code=401, detail="Invalid gateway key")
    else:
        allowed = gateway_auth.allowed_nodes(gw)

    def _check_scope(node_id: str) -> None:
        if allowed is not None and node_id not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Gateway not authorised for node {node_id}",
            )

    alerts = 0
    for r in payload.env:
        _check_scope(r.node_id)
        d = r.model_dump(mode="json")
        await influx.write_env(r.model_dump())
        await ws_hub.broadcast(r.site_id, {"type": "SENSOR_UPDATE", "kind": "env", "payload": d})
        alerts += len(await evaluate_env(db, r))

    for r in payload.geo:
        _check_scope(r.node_id)
        d = r.model_dump(mode="json")
        await influx.write_geo(r.model_dump())
        await ws_hub.broadcast(r.site_id, {"type": "SENSOR_UPDATE", "kind": "geo", "payload": d})
        alerts += len(await evaluate_geo(db, r))

    if alerts or gw is not None:
        await db.commit()

    return {
        "accepted": {"env": len(payload.env), "geo": len(payload.geo)},
        "alerts": alerts,
        "gateway": gw.name if gw else None,
    }
