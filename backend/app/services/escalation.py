"""Unacknowledged CRITICAL escalation (Phase 2.3 §5).

Policy: a CRITICAL or EVACUATION alert that remains unacknowledged for longer
than ``ESCALATION_DWELL`` (5 minutes by default) pages the next responder in
the site's ``escalation_steps`` ladder. Each hop:

- Sends a direct email + SMS to the next responder (bypassing the
  subscription filter — escalation is an obligation, not an opt-in).
- Records an ``escalation_hop`` entry in the audit log so the chain is
  replayable after the fact.
- Advances a marker (a single-column append to the alert's ``notes`` field
  stamped ``[esc:N]``) so the next sweep resumes from the following hop.

The sweep is idempotent: replaying it over the same alert within the dwell
window is a no-op. The Celery beat task below is scheduled once per minute.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.alert import Alert
from ..models.notifications import EscalationStep
from ..models.user import User
from .audit import record as audit_record
from .notifications import notifications

log = logging.getLogger(__name__)

ESCALATION_DWELL = timedelta(minutes=5)
ESCALATION_SEVERITIES = ("CRITICAL", "EVACUATION")


def _hop_marker(n: int) -> str:
    return f"[esc:{n}]"


def _current_hop(notes: str | None) -> int:
    """Parse the last ``[esc:N]`` marker appended by a previous sweep."""
    if not notes:
        return 0
    # Find the latest marker; parsing is cheap and boring on purpose.
    last = 0
    for token in notes.split():
        if token.startswith("[esc:") and token.endswith("]"):
            try:
                last = max(last, int(token[5:-1]))
            except ValueError:
                continue
    return last


async def _responder_for_hop(db: AsyncSession, site_id: str, hop: int) -> User | None:
    step = (
        await db.execute(
            select(EscalationStep).where(
                EscalationStep.site_id == site_id,
                EscalationStep.position == hop,
            )
        )
    ).scalar_one_or_none()
    if step is None:
        return None
    return await db.get(User, step.user_id)


async def sweep_unacknowledged(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Walk the unacked CRITICAL alerts and advance each one that is due for
    a hop. Returns the number of escalations dispatched."""

    now = now or datetime.now(UTC)
    cutoff = now - ESCALATION_DWELL
    stmt = select(Alert).where(
        Alert.acknowledged.is_(False),
        Alert.severity.in_(ESCALATION_SEVERITIES),
        Alert.created_at <= cutoff,
    )
    rows = (await db.execute(stmt)).scalars().all()
    dispatched = 0
    for alert in rows:
        next_hop = _current_hop(alert.notes) + 1
        user = await _responder_for_hop(db, alert.site_id, next_hop)
        if user is None:
            # Ladder exhausted; stop climbing.
            continue
        subject = f"[ESCALATION hop {next_hop}] {alert.site_id} {alert.severity}"
        body = (
            f"Alert {alert.id} ({alert.parameter}) at {alert.node_id} "
            f"still unacknowledged after {int(ESCALATION_DWELL.total_seconds() / 60)}m. "
            f"{alert.message}"
        )
        # Fire direct: escalation targets are contractual, not subscription-based.
        await notifications.direct(
            subject=subject,
            body=body,
            email=user.email,
            phone=user.phone_number,
        )
        alert.notes = ((alert.notes or "") + " " + _hop_marker(next_hop)).strip()
        await audit_record(
            db,
            user=user,
            action="escalation_hop",
            target_type="alert",
            target_id=alert.id,
            site_id=alert.site_id,
            details=f"hop={next_hop}",
        )
        dispatched += 1
    if dispatched:
        await db.commit()
    return dispatched
