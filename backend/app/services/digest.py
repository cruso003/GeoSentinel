"""Daily WATCH/WARNING email digest (Phase 2.3 §Digests).

The real-time pipeline (dispatch + escalation) covers CRITICAL /
EVACUATION. Everything below that bar is noise if pushed instantly but
valuable when batched — an operator who ignored a drifting pH warning at
3 a.m. wants to see it grouped with the four other WARNINGs from
overnight, not five pages each.

Design:

- One digest email per user per day. Aggregates alerts across every site
  the user has an *active email* subscription for, at severity
  ``WARNING`` or above. ``min_severity`` on each subscription still
  filters — if a user opted in at CRITICAL only, they get no digest
  (they already got real-time pages).
- Dedupes per (user, day): we stamp an ``audit`` row with
  ``action="digest_sent"`` + ``target_id=digest_key`` where
  ``digest_key = f"{user_id}:{day_iso}"``. Re-running the task within
  the same UTC day is a no-op for anyone already sent.
- Skips users with no matching alerts — digests never contain "nothing
  happened today".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.alert import Alert
from ..models.audit import AuditLog
from ..models.notifications import NotificationSubscription
from ..models.site import Site
from ..models.user import User
from . import audit
from .notifications import SEVERITY_RANK, NotificationService

log = logging.getLogger(__name__)


DIGEST_MIN_RANK = SEVERITY_RANK["WARNING"]
DIGEST_DEFAULT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class DigestSiteSection:
    site_id: str
    site_name: str
    alerts: tuple[Alert, ...]


@dataclass(frozen=True)
class UserDigest:
    user: User
    window_start: datetime
    window_end: datetime
    sections: tuple[DigestSiteSection, ...]

    @property
    def is_empty(self) -> bool:
        return all(not s.alerts for s in self.sections)

    @property
    def total_alerts(self) -> int:
        return sum(len(s.alerts) for s in self.sections)


def _digest_key(user_id: str, window_end: datetime) -> str:
    return f"{user_id}:{window_end.date().isoformat()}"


def render_plain(digest: UserDigest) -> tuple[str, str]:
    """Return ``(subject, body)`` plain-text rendering of the digest."""
    day = digest.window_end.date().isoformat()
    subject = f"[GeoSentinel] Daily digest · {day} · {digest.total_alerts} alerts"
    lines: list[str] = [
        f"Daily digest for {digest.user.name}",
        f"Window: {digest.window_start:%Y-%m-%d %H:%M UTC} → {digest.window_end:%Y-%m-%d %H:%M UTC}",
        "",
    ]
    for section in digest.sections:
        if not section.alerts:
            continue
        lines.append(f"== {section.site_name} ({section.site_id}) ==")
        for a in section.alerts:
            stamp = a.created_at.strftime("%H:%M") if a.created_at else "--:--"
            status = "ACK" if a.acknowledged else "open"
            lines.append(
                f"  [{a.severity:<10}] {stamp}  {a.alert_type:<16} {a.node_id}  "
                f"{a.parameter}  — {status}"
            )
            if a.message:
                lines.append(f"      {a.message[:160]}")
        lines.append("")
    lines.append(
        "CRITICAL / EVACUATION alerts are paged immediately — this digest"
        " only batches WARNING-level events you may have missed."
    )
    return subject, "\n".join(lines)


async def _already_sent_user_ids(
    db: AsyncSession, user_ids: list[str], window_end: datetime
) -> set[str]:
    """Return user ids that already received today's digest."""
    if not user_ids:
        return set()
    keys = {_digest_key(uid, window_end) for uid in user_ids}
    stmt = select(AuditLog.target_id).where(
        AuditLog.action == "digest_sent",
        AuditLog.target_id.in_(keys),
    )
    rows = (await db.execute(stmt)).scalars().all()
    already: set[str] = set()
    for key in rows:
        if key is None:
            continue
        uid, _, _ = key.partition(":")
        already.add(uid)
    return already


async def build_digests(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta = DIGEST_DEFAULT_WINDOW,
) -> list[UserDigest]:
    """Collect one ``UserDigest`` per active email subscriber with ≥1 alert
    in the window above their ``min_severity``. Skips users who already
    received today's digest."""

    window_end = now or datetime.now(UTC)
    window_start = window_end - window

    subs_stmt = (
        select(NotificationSubscription, User)
        .join(User, User.id == NotificationSubscription.user_id)
        .where(
            NotificationSubscription.channel == "email",
            NotificationSubscription.active.is_(True),
        )
    )
    sub_rows = (await db.execute(subs_stmt)).all()
    if not sub_rows:
        return []

    # Group (user, site) → min_severity rank so a user subscribed to both a
    # site and another inherits the most permissive threshold per site.
    per_user: dict[str, dict[str, int]] = {}
    user_lookup: dict[str, User] = {}
    for sub, user in sub_rows:
        min_rank = SEVERITY_RANK.get(sub.min_severity, 0)
        # A user who opted in at CRITICAL doesn't want a WARNING digest —
        # the digest floor is WARNING, so gate accordingly.
        if min_rank > DIGEST_MIN_RANK:
            continue
        by_site = per_user.setdefault(user.id, {})
        by_site[sub.site_id] = min(by_site.get(sub.site_id, min_rank), min_rank)
        user_lookup[user.id] = user

    if not per_user:
        return []

    already = await _already_sent_user_ids(db, list(per_user.keys()), window_end)

    site_ids = sorted({s for by_site in per_user.values() for s in by_site})
    site_rows = (
        await db.execute(select(Site).where(Site.id.in_(site_ids)))
    ).scalars().all()
    sites_by_id = {s.id: s for s in site_rows}

    alerts_stmt = select(Alert).where(
        and_(
            Alert.site_id.in_(site_ids),
            Alert.created_at >= window_start,
            Alert.created_at < window_end,
        )
    )
    alert_rows = (await db.execute(alerts_stmt)).scalars().all()

    alerts_by_site: dict[str, list[Alert]] = {s: [] for s in site_ids}
    for a in alert_rows:
        if a.site_id in alerts_by_site:
            alerts_by_site[a.site_id].append(a)
    for lst in alerts_by_site.values():
        lst.sort(key=lambda a: (a.created_at or window_start), reverse=True)

    digests: list[UserDigest] = []
    for user_id, by_site in per_user.items():
        if user_id in already:
            continue
        sections: list[DigestSiteSection] = []
        for site_id, min_rank in sorted(by_site.items()):
            site = sites_by_id.get(site_id)
            if site is None:
                continue
            relevant = tuple(
                a
                for a in alerts_by_site.get(site_id, ())
                if SEVERITY_RANK.get(a.severity, 0) >= max(min_rank, DIGEST_MIN_RANK)
            )
            if not relevant:
                continue
            sections.append(
                DigestSiteSection(
                    site_id=site_id, site_name=site.name, alerts=relevant
                )
            )
        if not sections:
            continue
        digests.append(
            UserDigest(
                user=user_lookup[user_id],
                window_start=window_start,
                window_end=window_end,
                sections=tuple(sections),
            )
        )
    return digests


async def send_digests(
    db: AsyncSession,
    *,
    service: NotificationService,
    now: datetime | None = None,
) -> dict:
    """Build + send today's digests. Returns a summary dict suitable for
    returning from a Celery task (``{"sent": N, "skipped": M}``)."""

    digests = await build_digests(db, now=now)
    sent = 0
    for digest in digests:
        subject, body = render_plain(digest)
        await service.direct(
            subject=subject,
            body=body,
            email=digest.user.email,
        )
        await audit.record(
            db,
            user=digest.user,
            action="digest_sent",
            target_type="digest",
            target_id=_digest_key(digest.user.id, digest.window_end),
            details=f"alerts={digest.total_alerts};sites={len(digest.sections)}",
        )
        sent += 1

    if sent:
        await db.commit()
    log.info("digest.send sent=%d considered=%d", sent, len(digests))
    return {"sent": sent, "considered": len(digests)}
