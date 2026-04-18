"""Audit hash-chain computation (Phase 2.1 §9).

We exercise the pure functions — `_canonical` and `_hash_row` — without
touching the database. The chain structure is:

    row_hash[n] = sha256( row_hash[n-1] || canonical_json(row[n]) )

which means *any* field change (including the hash columns themselves,
except that those are excluded from canonical_json) invalidates the rest
of the chain from that row forward.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

from app.services import audit as audit_service  # noqa: E402


@dataclass
class FakeRow:
    id: str
    actor_email: str
    actor_role: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    site_id: str | None = None
    ip_address: str | None = None
    details: str | None = None
    created_at: datetime | None = None
    prev_hash: str | None = None
    row_hash: str | None = None


def _fresh(**kw) -> FakeRow:
    defaults = dict(
        id="row-1",
        actor_email="a@b.co",
        actor_role="operator",
        action="login",
        created_at=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(kw)
    return FakeRow(**defaults)


def test_canonical_is_deterministic():
    r = _fresh()
    assert audit_service._canonical(r) == audit_service._canonical(r)


def test_canonical_excludes_hash_columns():
    r1 = _fresh(row_hash="AAA", prev_hash="BBB")
    r2 = _fresh(row_hash=None, prev_hash=None)
    assert audit_service._canonical(r1) == audit_service._canonical(r2)


def test_hash_row_is_deterministic_for_same_inputs():
    r = _fresh()
    assert audit_service._hash_row("prev", r) == audit_service._hash_row("prev", r)


def test_hash_row_changes_when_content_changes():
    r1 = _fresh(details="ok")
    r2 = _fresh(details="ok tampered")
    assert audit_service._hash_row("prev", r1) != audit_service._hash_row("prev", r2)


def test_hash_row_depends_on_prev_hash():
    r = _fresh()
    assert audit_service._hash_row("prev-A", r) != audit_service._hash_row("prev-B", r)


def test_chain_links_forward():
    r1 = _fresh(id="row-1", action="login")
    r2 = _fresh(
        id="row-2",
        action="alert.ack",
        created_at=datetime(2026, 4, 17, 12, 5, tzinfo=timezone.utc),
    )
    h1 = audit_service._hash_row("", r1)
    r1.row_hash = h1
    r2.prev_hash = h1
    h2 = audit_service._hash_row(h1, r2)
    r2.row_hash = h2

    # Flipping r1's action busts h1 and therefore r2's stored prev_hash is
    # no longer the correct recomputation.
    tampered = _fresh(id="row-1", action="login.spoofed")
    assert audit_service._hash_row("", tampered) != h1
