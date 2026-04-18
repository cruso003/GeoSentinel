"""Admin-only model registry (Phase 2.4 §5).

Endpoints:

  GET  /models/{name}/versions        — history with stages + metrics
  GET  /models/{name}/production      — currently-served version, or 404
  POST /models/{name}/versions        — register a candidate (used by
                                        the trainer / CI once artifacts
                                        are signed and uploaded)
  POST /models/{name}/versions/{id}/promote
                                      — run the gate; promote on pass,
                                        land the attempt in the hash-
                                        chain audit regardless

``esg_admin`` is the only role allowed here — operators can inspect
predictions, but swapping the model that produces them is a separately-
authorised action.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import require_roles
from ...models.model_version import ModelVersion
from ...models.user import User
from ...schemas.models import (
    ModelVersionIn,
    ModelVersionOut,
    PromoteRequest,
    PromoteResponse,
)
from ...services import model_registry

router = APIRouter(prefix="/models", tags=["models"])

esg_admin = require_roles("esg_admin")


@router.get("/{name}/versions", response_model=list[ModelVersionOut])
async def list_versions(
    _: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: Annotated[str, Path()],
):
    rows = (
        await db.execute(
            select(ModelVersion)
            .where(ModelVersion.name == name)
            .order_by(ModelVersion.created_at.desc())
        )
    ).scalars().all()
    return [ModelVersionOut.from_row(r) for r in rows]


@router.get("/{name}/production", response_model=ModelVersionOut)
async def get_production(
    _: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: Annotated[str, Path()],
):
    row = await model_registry.get_production(db, name)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"No production version for {name!r}"
        )
    return ModelVersionOut.from_row(row)


@router.post(
    "/{name}/versions",
    response_model=ModelVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def register_version(
    body: ModelVersionIn,
    _: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: Annotated[str, Path()],
):
    if body.name != name:
        raise HTTPException(
            status_code=400,
            detail=f"Body name {body.name!r} does not match path {name!r}",
        )
    row = await model_registry.register_candidate(
        db,
        name=body.name,
        version=body.version,
        metrics=body.metrics,
        data_sha256=body.data_sha256,
        artifact_uri=body.artifact_uri,
        mlflow_run_id=body.mlflow_run_id,
    )
    await db.commit()
    await db.refresh(row)
    return ModelVersionOut.from_row(row)


@router.post(
    "/{name}/versions/{version_id}/promote",
    response_model=PromoteResponse,
)
async def promote_version(
    body: PromoteRequest,
    user: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: Annotated[str, Path()],
    version_id: Annotated[str, Path()],
):
    row = await model_registry.get_version(db, version_id)
    if row is None or row.name != name:
        raise HTTPException(status_code=404, detail="Model version not found")
    result = await model_registry.promote(db, version=row, user=user, force=body.force)
    await db.commit()
    await db.refresh(row)
    return PromoteResponse(
        promoted=result["promoted"],
        gate=result["gate"],
        version=ModelVersionOut.from_row(row),
    )
