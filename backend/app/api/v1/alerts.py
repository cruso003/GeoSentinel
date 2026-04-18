"""Alert endpoints (Spec §5.2.5)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import get_current_user, require_roles
from ...models.alert import Alert
from ...models.user import User
from ...schemas.entities import AlertAcknowledge, AlertOut
from ...services import audit
from ...services.rbac import allowed_site_ids
from ...services.ws_hub import ws_hub

router = APIRouter(prefix="/alerts", tags=["alerts"])

operator_or_admin = require_roles("operator", "esg_admin")


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    user: Annotated[User, Depends(operator_or_admin)],
    site_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    ids = await allowed_site_ids(db, user)
    if not ids:
        return []
    stmt = (
        select(Alert)
        .where(Alert.site_id.in_(ids))
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if site_id:
        if site_id not in ids:
            raise HTTPException(status_code=403, detail="Forbidden")
        stmt = stmt.where(Alert.site_id == site_id)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged == acknowledged)
    rows = (await db.execute(stmt)).scalars().all()
    return [AlertOut.model_validate(a) for a in rows]


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: str,
    user: Annotated[User, Depends(operator_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    a = await db.get(Alert, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    ids = await allowed_site_ids(db, user)
    if a.site_id not in ids:
        raise HTTPException(status_code=403, detail="Forbidden")
    return AlertOut.model_validate(a)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: str,
    body: AlertAcknowledge,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if user.role not in ("operator", "esg_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    a = await db.get(Alert, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    ids = await allowed_site_ids(db, user)
    if a.site_id not in ids:
        raise HTTPException(status_code=403, detail="Forbidden")
    a.acknowledged = True
    a.acknowledged_by = user.email
    a.acknowledged_at = datetime.now(UTC)
    if body.notes:
        a.notes = body.notes
    await audit.record(
        db,
        user=user,
        action="acknowledge_alert",
        target_type="alert",
        target_id=a.id,
        site_id=a.site_id,
        details=body.notes,
    )
    await db.commit()
    await db.refresh(a)
    await ws_hub.broadcast(
        a.site_id,
        {"type": "ALERT_ACKNOWLEDGED", "alert_id": a.id, "by": user.email},
    )
    return AlertOut.model_validate(a)
