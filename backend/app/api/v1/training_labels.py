"""Admin-only training-label ingestion (Phase 2.4)."""

from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import require_roles
from ...models.training_label import TrainingLabel
from ...models.user import User
from ...schemas.training_labels import TrainingLabelIn, TrainingLabelOut
from ...services import audit

router = APIRouter(prefix="/training-labels", tags=["training-labels"])

esg_admin = require_roles("esg_admin")


@router.get("", response_model=list[TrainingLabelOut])
async def list_labels(
    _: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    site_id: str | None = Query(default=None),
    parameter: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    stmt = select(TrainingLabel).order_by(TrainingLabel.t_start.desc()).limit(limit)
    if site_id:
        stmt = stmt.where(TrainingLabel.site_id == site_id)
    if parameter:
        stmt = stmt.where(TrainingLabel.parameter == parameter)
    if source:
        stmt = stmt.where(TrainingLabel.source == source)
    rows = (await db.execute(stmt)).scalars().all()
    return [TrainingLabelOut.model_validate(r) for r in rows]


@router.post("", response_model=TrainingLabelOut, status_code=status.HTTP_201_CREATED)
async def create_label(
    body: TrainingLabelIn,
    user: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = TrainingLabel(**body.model_dump())
    db.add(row)
    await audit.record(
        db,
        user=user,
        action="create_training_label",
        target_type="training_label",
        site_id=body.site_id,
        details=f"param={body.parameter};source={body.source}",
    )
    await db.commit()
    await db.refresh(row)
    return TrainingLabelOut.model_validate(row)


# Column order matches the CSV schema documented in
# ``docs/ops/training-label-csv.md`` (to be written alongside the first real
# import). Header row is required; unknown columns are ignored so evaluators
# can add metadata without breaking the importer.
_EXPECTED_COLUMNS = (
    "site_id",
    "node_id",
    "parameter",
    "t_start",
    "t_end",
    "label",
    "source",
    "notes",
)


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_labels(
    user: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Bulk-upload a CSV of training labels. Rows that fail validation are
    reported in the response so the operator can fix them offline — the rest
    still land."""

    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is empty or missing header")
    missing = [c for c in _EXPECTED_COLUMNS if c not in reader.fieldnames and c != "notes"]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"CSV missing required columns: {missing}"
        )

    accepted = 0
    errors: list[dict] = []
    for lineno, row in enumerate(reader, start=2):  # header is line 1
        try:
            body = TrainingLabelIn(
                site_id=row["site_id"].strip(),
                node_id=row["node_id"].strip(),
                parameter=row["parameter"].strip(),
                t_start=row["t_start"].strip(),
                t_end=row["t_end"].strip(),
                label=row["label"].strip(),
                source=row["source"].strip(),
                notes=(row.get("notes") or "").strip() or None,
            )
        except Exception as e:
            errors.append({"line": lineno, "error": str(e)})
            continue
        db.add(TrainingLabel(**body.model_dump()))
        accepted += 1

    await audit.record(
        db,
        user=user,
        action="import_training_labels",
        target_type="training_label",
        details=f"accepted={accepted};errors={len(errors)}",
    )
    await db.commit()
    return {"accepted": accepted, "errors": errors}
