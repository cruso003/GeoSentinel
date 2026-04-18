"""Per-site RBAC helpers (Phase 2.3 §3)."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

from app.services.rbac import allowed_site_ids, user_can_access_site


@dataclass
class _User:
    id: str
    role: str


def _db_returning(memberships: list[str], all_sites: list[str] | None = None):
    """Build an AsyncMock that mimics SQLAlchemy's ``await db.execute(...)``
    pattern. Returns ``memberships`` from the first call (user_sites query)
    and ``all_sites`` from a second call (sites fallback) when supplied."""
    db = MagicMock()
    results: list[MagicMock] = []

    membership_scalars = MagicMock()
    membership_scalars.all = MagicMock(return_value=memberships)
    first = MagicMock()
    first.scalars = MagicMock(return_value=membership_scalars)
    results.append(first)

    if all_sites is not None:
        all_scalars = MagicMock()
        all_scalars.all = MagicMock(return_value=all_sites)
        second = MagicMock()
        second.scalars = MagicMock(return_value=all_scalars)
        results.append(second)

    db.execute = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_allowed_site_ids_prefers_memberships():
    db = _db_returning(memberships=["tokadeh", "bomi"])
    user = _User(id="u1", role="operator")
    assert await allowed_site_ids(db, user) == ["tokadeh", "bomi"]


@pytest.mark.asyncio
async def test_allowed_site_ids_operator_with_no_memberships_is_empty():
    db = _db_returning(memberships=[])
    user = _User(id="u1", role="operator")
    assert await allowed_site_ids(db, user) == []


@pytest.mark.asyncio
async def test_allowed_site_ids_esg_admin_falls_through_to_all_sites():
    db = _db_returning(memberships=[], all_sites=["tokadeh", "bomi", "yekepa"])
    user = _User(id="u1", role="esg_admin")
    assert await allowed_site_ids(db, user) == ["tokadeh", "bomi", "yekepa"]


@pytest.mark.asyncio
async def test_user_can_access_site_rejects_wrong_role():
    db = MagicMock()
    user = _User(id="u1", role="community")
    assert not await user_can_access_site(
        db, user, "tokadeh", roles=("operator", "esg_admin")
    )


def _db_membership_row(site_id: str, role: str):
    @dataclass
    class _Row:
        site_id: str
        role: str

    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=_Row(site_id=site_id, role=role))
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_user_can_access_site_accepts_when_membership_matches():
    db = _db_membership_row("tokadeh", "operator")
    user = _User(id="u1", role="operator")
    assert await user_can_access_site(
        db, user, "tokadeh", roles=("operator", "esg_admin")
    )


@pytest.mark.asyncio
async def test_user_can_access_site_membership_role_must_be_allowed():
    # Platform role is operator, but membership was downgraded to community.
    db = _db_membership_row("tokadeh", "community")
    user = _User(id="u1", role="operator")
    assert not await user_can_access_site(
        db, user, "tokadeh", roles=("operator", "esg_admin")
    )


@pytest.mark.asyncio
async def test_user_can_access_site_esg_admin_without_membership_allowed():
    db = MagicMock()
    none_result = MagicMock()
    none_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=none_result)
    user = _User(id="u1", role="esg_admin")
    assert await user_can_access_site(
        db, user, "tokadeh", roles=("operator", "esg_admin")
    )
