"""Liveness + readiness probes (Phase 2.2).

Liveness: "is the process up and the event loop responsive?" — used by
Docker/K8s to decide whether to restart.

Readiness: "can I serve real traffic?" — checks Postgres, Redis, and the
InfluxDB client. Failures don't crash the app (those are the fallback
paths), but the endpoint returns 503 so the load balancer stops routing
to a node that can't talk to its dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..services.influx import influx

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_PROBE_TIMEOUT_S = 2.0


async def _check_db(db: AsyncSession) -> bool:
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=_PROBE_TIMEOUT_S)
        return True
    except Exception as e:
        log.info("readiness: postgres check failed (%s)", e)
        return False


async def _check_redis() -> bool:
    try:
        import redis.asyncio as aioredis  # type: ignore
    except Exception:
        return True  # Redis is optional; fallback paths cover it.
    from ..core.config import get_settings

    try:
        client = aioredis.from_url(get_settings().redis_url)
        await asyncio.wait_for(client.ping(), timeout=_PROBE_TIMEOUT_S)
        await client.close()
        return True
    except Exception as e:
        log.info("readiness: redis check failed (%s)", e)
        return False


async def _check_influx() -> bool:
    # We consider Influx healthy if the client either connected at startup
    # or the in-memory fallback path is in play (no-op check). Either way
    # the app can serve; the ring buffer keeps hot reads alive.
    return True if influx is not None else False


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    checks = await asyncio.gather(
        _check_db(db), _check_redis(), _check_influx(), return_exceptions=False
    )
    names = ("postgres", "redis", "influx")
    result = dict(zip(names, checks))
    ok = all(checks)
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ok": ok, **result}
