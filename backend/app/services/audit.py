"""Audit log writer (Spec §8.6) with tamper-evident hash chain (Phase 2.1 §9).

Each row's `row_hash` is ``sha256(prev_hash || canonical_json(payload))``.
The canonical payload is a sorted-key JSON dump of the row's own fields,
excluding the hash columns themselves. `verify_chain()` recomputes the
chain and returns the first break.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog
from ..models.user import User


def _canonical(row: AuditLog) -> bytes:
    payload = {
        "id": row.id,
        "actor_email": row.actor_email,
        "actor_role": row.actor_role,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "site_id": row.site_id,
        "ip_address": row.ip_address,
        "details": row.details,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_row(prev_hash: str, row: AuditLog) -> str:
    h = hashlib.sha256()
    h.update((prev_hash or "").encode("utf-8"))
    h.update(_canonical(row))
    return h.hexdigest()


async def _latest_hash(db: AsyncSession) -> str:
    row = (
        await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return row.row_hash if row and row.row_hash else ""


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
        created_at=datetime.now(timezone.utc),
    )
    prev = await _latest_hash(db)
    entry.prev_hash = prev or None
    entry.row_hash = _hash_row(prev, entry)
    db.add(entry)
    await db.flush()
    return entry


async def verify_chain(db: AsyncSession) -> dict:
    """Walk the log in insert order and return the first mismatch (if any)."""
    rows = (
        await db.execute(select(AuditLog).order_by(AuditLog.created_at.asc()))
    ).scalars().all()
    prev = ""
    for r in rows:
        expected = _hash_row(prev, r)
        if (r.prev_hash or "") != prev or r.row_hash != expected:
            return {
                "ok": False,
                "broken_at": r.id,
                "broken_created_at": r.created_at.isoformat() if r.created_at else None,
                "expected_prev": prev,
                "stored_prev": r.prev_hash,
                "expected_row_hash": expected,
                "stored_row_hash": r.row_hash,
            }
        prev = r.row_hash or ""
    return {"ok": True, "rows": len(rows), "head": prev or None}
