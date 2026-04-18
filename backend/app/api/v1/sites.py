from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.db import get_db
from ...core.deps import require_roles, require_site_role
from ...models.site import MineSlope, SensorNode, Site
from ...models.user import User
from ...schemas.entities import MineSlopeOut, SensorNodeOut, SiteOut, SiteSummary
from ...services.rbac import allowed_site_ids

router = APIRouter(prefix="/sites", tags=["sites"])

operator_or_admin = require_roles("operator", "esg_admin")
site_scoped_operator = require_site_role("operator", "esg_admin")


@router.get("", response_model=list[SiteSummary])
async def list_sites(
    user: Annotated[User, Depends(operator_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    ids = await allowed_site_ids(db, user)
    if not ids:
        return []
    rows = (await db.execute(select(Site).where(Site.id.in_(ids)))).scalars().all()
    return [
        SiteSummary(
            id=s.id,
            name=s.name,
            region=s.region,
            country=s.country,
            centroid={"lat": s.centroid_lat, "lng": s.centroid_lng},
        )
        for s in rows
    ]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: str,
    _=Depends(site_scoped_operator),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    site = (
        await db.execute(
            select(Site)
            .where(Site.id == site_id)
            .options(selectinload(Site.nodes), selectinload(Site.slopes))
        )
    ).scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut(
        id=site.id,
        name=site.name,
        region=site.region,
        country=site.country,
        centroid={"lat": site.centroid_lat, "lng": site.centroid_lng},
        boundary=site.boundary_geojson,
        nodes=[SensorNodeOut.model_validate(n) for n in site.nodes],
        slopes=[
            MineSlopeOut(
                id=s.id,
                site_id=s.site_id,
                name=s.name,
                geometry=s.geometry_geojson,
                mesh_vertices=s.mesh_vertices,
            )
            for s in site.slopes
        ],
    )


@router.get("/{site_id}/nodes", response_model=list[SensorNodeOut])
async def list_nodes(
    site_id: str,
    _=Depends(site_scoped_operator),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    rows = (
        await db.execute(select(SensorNode).where(SensorNode.site_id == site_id))
    ).scalars().all()
    return [SensorNodeOut.model_validate(n) for n in rows]


@router.get("/{site_id}/nodes/{node_id}", response_model=SensorNodeOut)
async def get_node(
    site_id: str,
    node_id: str,
    _=Depends(site_scoped_operator),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    node = (
        await db.execute(
            select(SensorNode).where(SensorNode.site_id == site_id, SensorNode.id == node_id)
        )
    ).scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return SensorNodeOut.model_validate(node)


@router.get("/{site_id}/slopes", response_model=list[MineSlopeOut])
async def list_slopes(
    site_id: str,
    _=Depends(site_scoped_operator),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    rows = (
        await db.execute(select(MineSlope).where(MineSlope.site_id == site_id))
    ).scalars().all()
    return [
        MineSlopeOut(
            id=s.id,
            site_id=s.site_id,
            name=s.name,
            geometry=s.geometry_geojson,
            mesh_vertices=s.mesh_vertices,
        )
        for s in rows
    ]
