"""Admin endpoints for provisioning sensor gateway credentials (Phase 2.1 §7).

POST /gateways — mint a new key (plaintext returned once)
POST /gateways/{id}/rotate — replace the key; plaintext returned once
POST /gateways/{id}/deactivate — set active=False without deleting history
GET  /gateways — list gateways for a site (no plaintext, no hash)
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import require_roles
from ...models.gateway import SensorGateway
from ...models.user import User
from ...services import audit, gateway_auth

router = APIRouter(prefix="/gateways", tags=["gateways"])

admin_only = require_roles("esg_admin")


class GatewayCreate(BaseModel):
    site_id: str
    name: str = Field(min_length=1, max_length=255)
    allowed_node_ids: Optional[list[str]] = None


class GatewayOut(BaseModel):
    id: str
    site_id: str
    name: str
    key_prefix: str
    allowed_node_ids: Optional[list[str]]
    active: bool


class GatewayMinted(GatewayOut):
    plaintext_key: str  # shown once at creation/rotation time


@router.get("", response_model=list[GatewayOut])
async def list_gateways(
    site_id: Optional[str] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _=Depends(admin_only),
):
    stmt = select(SensorGateway)
    if site_id:
        stmt = stmt.where(SensorGateway.site_id == site_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [GatewayOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=GatewayMinted, status_code=201)
async def create_gateway(
    body: GatewayCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(admin_only)],
):
    plaintext, prefix, hashed = gateway_auth.mint_key()
    row = SensorGateway(
        site_id=body.site_id,
        name=body.name,
        key_prefix=prefix,
        hashed_key=hashed,
        allowed_node_ids=body.allowed_node_ids,
    )
    db.add(row)
    await db.flush()
    await audit.record(
        db, user=actor, action="gateway.create",
        target_type="sensor_gateway", target_id=row.id, site_id=row.site_id,
        details=json.dumps({"name": row.name, "key_prefix": prefix}),
    )
    await db.commit()
    return GatewayMinted(
        id=row.id, site_id=row.site_id, name=row.name, key_prefix=row.key_prefix,
        allowed_node_ids=row.allowed_node_ids, active=row.active,
        plaintext_key=plaintext,
    )


@router.post("/{gw_id}/rotate", response_model=GatewayMinted)
async def rotate_gateway(
    gw_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(admin_only)],
):
    row = await db.get(SensorGateway, gw_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    plaintext, prefix, hashed = gateway_auth.mint_key()
    row.key_prefix = prefix
    row.hashed_key = hashed
    await audit.record(
        db, user=actor, action="gateway.rotate",
        target_type="sensor_gateway", target_id=row.id, site_id=row.site_id,
        details=json.dumps({"key_prefix": prefix}),
    )
    await db.commit()
    return GatewayMinted(
        id=row.id, site_id=row.site_id, name=row.name, key_prefix=row.key_prefix,
        allowed_node_ids=row.allowed_node_ids, active=row.active,
        plaintext_key=plaintext,
    )


@router.post("/{gw_id}/deactivate", response_model=GatewayOut)
async def deactivate_gateway(
    gw_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(admin_only)],
):
    row = await db.get(SensorGateway, gw_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Gateway not found")
    row.active = False
    await audit.record(
        db, user=actor, action="gateway.deactivate",
        target_type="sensor_gateway", target_id=row.id, site_id=row.site_id,
    )
    await db.commit()
    return GatewayOut.model_validate(row, from_attributes=True)
