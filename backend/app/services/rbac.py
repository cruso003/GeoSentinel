"""Per-site RBAC (Phase 2.3 §3).

The platform historically granted access purely on the user's ``role`` —
any ``operator`` could see any site. For multi-tenant pilot deployments we
now also scope by membership in the ``user_sites`` join table.

Rules:

- ``esg_admin`` users remain global admins. Listing all sites without an
  explicit ``user_sites`` row is intentional: a regulator who audits all
  concessions shouldn't need a membership row per site. Per-site admin
  scoping is opt-in via the ``user_sites`` membership.
- Every other role must have an active ``user_sites`` row for the target
  site, and their membership ``role`` there must match one of the allowed
  roles for the route.
- The ``community`` role has zero default visibility — the community
  dashboard remains public and unauthenticated (Spec §5.2.7).

Functions here are pure services; FastAPI dependencies wrap them in
``core/deps.py``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.notifications import UserSite
from ..models.site import Site
from ..models.user import User


async def allowed_site_ids(db: AsyncSession, user: User) -> list[str]:
    """Return the site ids the user is permitted to query.

    - ``esg_admin`` with no explicit memberships sees everything.
    - Otherwise: only sites present in ``user_sites`` for this user.
    """
    memberships = (
        await db.execute(select(UserSite.site_id).where(UserSite.user_id == user.id))
    ).scalars().all()
    if memberships:
        return list(memberships)
    if user.role == "esg_admin":
        return (await db.execute(select(Site.id))).scalars().all()
    return []


async def user_can_access_site(
    db: AsyncSession, user: User, site_id: str, *, roles: tuple[str, ...]
) -> bool:
    """``True`` iff the user may act on ``site_id`` with one of ``roles``."""
    if user.role not in roles:
        # Fast reject: platform-level role isn't even plausible for this route.
        # Admin-only routes pass ("esg_admin",) and a member-mismatch still 403s.
        return False
    row = (
        await db.execute(
            select(UserSite).where(
                UserSite.user_id == user.id, UserSite.site_id == site_id
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row.role in roles
    # No membership row. esg_admin falls through to global admin.
    return user.role == "esg_admin"
