"""Audit log query + CSV export (Spec §8.6, §14)."""

import csv
import io
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import require_roles
from ...models.audit import AuditLog
from ...services import audit as audit_service
from ...services.csv_safe import csv_safe

router = APIRouter(prefix="/audit", tags=["audit"])

esg_admin_only = require_roles("esg_admin")


@router.get("")
async def list_audit(
    action: Optional[str] = Query(default=None),
    site_id: Optional[str] = Query(default=None),
    actor_email: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> List[dict]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if site_id:
        stmt = stmt.where(AuditLog.site_id == site_id)
    if actor_email:
        stmt = stmt.where(AuditLog.actor_email == actor_email)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "actor_email": r.actor_email,
            "actor_role": r.actor_role,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "site_id": r.site_id,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/verify")
async def verify_audit_chain(
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Recompute the sha256 chain. Returns {ok: true/false, ...}."""
    return await audit_service.verify_chain(db)


@router.get("/export.csv")
async def export_audit_csv(
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "actor_email", "actor_role", "action",
                "target_type", "target_id", "site_id", "details"])
    for r in rows:
        details = (r.details or "").replace("\n", " ").replace("\r", " ")
        w.writerow([
            csv_safe(r.id),
            r.created_at.isoformat() if r.created_at else "",
            csv_safe(r.actor_email),
            csv_safe(r.actor_role),
            csv_safe(r.action),
            csv_safe(r.target_type),
            csv_safe(r.target_id),
            csv_safe(r.site_id),
            csv_safe(details),
        ])
    buf.seek(0)
    fname = f"geosentinel-audit-{datetime.now(timezone.utc).date()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
