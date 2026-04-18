"""AI inference endpoints (Spec §5.2.4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import require_roles, require_site_role
from ...models.site import MineSlope, Site
from ...models.user import User
from ...schemas.ai import (
    EnviroGuardPredictionOut,
    InferenceRunRequest,
    SlopeWatchPredictionOut,
)
from ...services.enviroguard import run_enviroguard
from ...services.rbac import user_can_access_site
from ...services.slopewatch import run_slopewatch
from ...services.ws_hub import ws_hub

router = APIRouter(prefix="/ai", tags=["ai"])

operator_or_admin = require_site_role("operator", "esg_admin")
any_operator_or_admin = require_roles("operator", "esg_admin")


@router.get("/enviroguard/predictions/{site_id}", response_model=EnviroGuardPredictionOut)
async def enviroguard_latest(
    site_id: str,
    _=Depends(operator_or_admin),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return await run_enviroguard(site_id)


@router.get("/slopewatch/predictions/{site_id}", response_model=list[SlopeWatchPredictionOut])
async def slopewatch_latest(
    site_id: str,
    _=Depends(operator_or_admin),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    slopes = (
        await db.execute(select(MineSlope.id).where(MineSlope.site_id == site_id))
    ).scalars().all()
    if not slopes:
        raise HTTPException(status_code=404, detail="No slopes for site")
    return await run_slopewatch(site_id, list(slopes))


@router.post("/enviroguard/run", response_model=EnviroGuardPredictionOut)
async def enviroguard_run(
    body: InferenceRunRequest,
    user: Annotated[User, Depends(any_operator_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if not await user_can_access_site(db, user, body.site_id, roles=("operator", "esg_admin")):
        raise HTTPException(status_code=403, detail="Forbidden")
    site = await db.get(Site, body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    pred = await run_enviroguard(body.site_id)
    await ws_hub.broadcast(body.site_id, {"type": "AI_PREDICTION", "model": "enviroguard", "payload": pred.model_dump(mode="json")})
    return pred


@router.post("/slopewatch/run", response_model=list[SlopeWatchPredictionOut])
async def slopewatch_run(
    body: InferenceRunRequest,
    user: Annotated[User, Depends(any_operator_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if not await user_can_access_site(db, user, body.site_id, roles=("operator", "esg_admin")):
        raise HTTPException(status_code=403, detail="Forbidden")
    slopes = (
        await db.execute(select(MineSlope.id).where(MineSlope.site_id == body.site_id))
    ).scalars().all()
    if not slopes:
        raise HTTPException(status_code=404, detail="No slopes for site")
    preds = await run_slopewatch(body.site_id, list(slopes))
    for p in preds:
        await ws_hub.broadcast(body.site_id, {"type": "AI_PREDICTION", "model": "slopewatch", "payload": p.model_dump(mode="json")})
    return preds
