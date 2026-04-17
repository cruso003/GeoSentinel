"""Audit log writer (Spec §8.6)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog
from ..models.user import User


async def record(
    db: AsyncSession,
    *,
    user: User,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    site_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        actor_email=user.email,
        actor_role=user.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        site_id=site_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(entry)
    await db.flush()
    return entry
