"""Daily digest service (Phase 2.3 §Digests).

Pure-logic coverage of the rendering + grouping. The DB-backed
``build_digests`` path is exercised with a mocked AsyncSession that
feeds ``execute()`` a fixed sequence of scalar results — enough to
verify the dedupe + severity-gate branches without standing up a
real database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import digest as digest_service
from app.services.digest import (
    DIGEST_MIN_RANK,
    DigestSiteSection,
    UserDigest,
    _digest_key,
    render_plain,
)
from app.services.notifications import SEVERITY_RANK

# --- fake row helpers -------------------------------------------------


@dataclass
class _Alert:
    id: str
    site_id: str
    node_id: str
    alert_type: str
    severity: str
    parameter: str
    message: str
    created_at: datetime
    acknowledged: bool = False


@dataclass
class _User:
    id: str
    email: str
    name: str
    role: str = "operator"
    phone_number: str | None = None


@dataclass
class _Sub:
    user_id: str
    site_id: str
    channel: str
    min_severity: str
    active: bool = True


@dataclass
class _Site:
    id: str
    name: str


def _now() -> datetime:
    return datetime(2026, 4, 18, 7, 0, tzinfo=UTC)


def _alert(**kw) -> _Alert:
    defaults = dict(
        id="a",
        site_id="tokadeh-pilot",
        node_id="ENV-01",
        alert_type="ENV_THRESHOLD",
        severity="WARNING",
        parameter="ph",
        message="pH slipping",
        created_at=_now() - timedelta(hours=3),
        acknowledged=False,
    )
    defaults.update(kw)
    return _Alert(**defaults)


def _mock_db(sub_rows, sites, alerts, already_sent_keys=()):
    """Feeds Scalar results in the sequence used by ``build_digests``:

    1. subscription+user join → list of (sub, user) tuples
    2. already_sent audit lookup → list of keys
    3. site lookup by ids → list of Site rows
    4. alerts lookup → list of Alert rows
    """

    db = MagicMock()
    db.execute = AsyncMock()

    class _ScalarList:
        def __init__(self, values):
            self._values = list(values)

        def scalars(self):
            return self

        def all(self):
            return list(self._values)

    class _Rows:
        def __init__(self, rows):
            self._rows = list(rows)

        def all(self):
            return list(self._rows)

        def scalars(self):
            return _ScalarList(
                [r[0] if isinstance(r, tuple) else r for r in self._rows]
            )

    db.execute.side_effect = [
        _Rows(sub_rows),
        _ScalarList(list(already_sent_keys)),
        _Rows(sites),
        _Rows(alerts),
    ]
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# --- render_plain -----------------------------------------------------


def test_render_plain_includes_site_header_and_counts():
    user = _User(id="u1", email="op@x.com", name="Op")
    section = DigestSiteSection(
        site_id="tokadeh-pilot",
        site_name="Tokadeh",
        alerts=(
            _alert(severity="WARNING", message="pH drifting low"),
            _alert(severity="CRITICAL", message="pH breach"),
        ),
    )
    digest = UserDigest(
        user=user,
        window_start=_now() - timedelta(hours=24),
        window_end=_now(),
        sections=(section,),
    )
    subject, body = render_plain(digest)
    assert "Daily digest" in subject
    assert "2 alerts" in subject
    assert "Tokadeh" in body
    assert "WARNING" in body
    assert "CRITICAL" in body
    assert "pH drifting low" in body


def test_digest_key_uses_utc_date():
    assert _digest_key("u1", datetime(2026, 4, 18, 23, 59, tzinfo=UTC)) == "u1:2026-04-18"


# --- build_digests ----------------------------------------------------


@pytest.mark.asyncio
async def test_build_digest_groups_by_site_and_filters_below_warning():
    user = _User(id="u1", email="op@x.com", name="Op")
    sub = _Sub(user_id="u1", site_id="tokadeh-pilot", channel="email", min_severity="WARNING")
    site = _Site(id="tokadeh-pilot", name="Tokadeh")
    alerts = [
        _alert(id="a1", severity="INFO"),  # below DIGEST_MIN_RANK — filtered
        _alert(id="a2", severity="WARNING"),
        _alert(id="a3", severity="CRITICAL"),
    ]
    db = _mock_db([(sub, user)], [site], alerts)

    digests = await digest_service.build_digests(db, now=_now())
    assert len(digests) == 1
    d = digests[0]
    assert d.total_alerts == 2
    ids = {a.id for a in d.sections[0].alerts}
    assert ids == {"a2", "a3"}


@pytest.mark.asyncio
async def test_build_digest_skips_critical_only_subscribers():
    # Opted in at CRITICAL → doesn't want WARNING batch.
    user = _User(id="u1", email="critic@x.com", name="Critic")
    sub = _Sub(
        user_id="u1", site_id="tokadeh-pilot", channel="email", min_severity="CRITICAL"
    )
    site = _Site(id="tokadeh-pilot", name="Tokadeh")
    alerts = [_alert(severity="WARNING"), _alert(severity="CRITICAL")]
    db = _mock_db([(sub, user)], [site], alerts)

    digests = await digest_service.build_digests(db, now=_now())
    assert digests == []


@pytest.mark.asyncio
async def test_build_digest_skips_empty_sections():
    user = _User(id="u1", email="op@x.com", name="Op")
    sub = _Sub(user_id="u1", site_id="tokadeh-pilot", channel="email", min_severity="WARNING")
    site = _Site(id="tokadeh-pilot", name="Tokadeh")
    db = _mock_db([(sub, user)], [site], [])

    digests = await digest_service.build_digests(db, now=_now())
    assert digests == []


@pytest.mark.asyncio
async def test_build_digest_honours_sent_dedupe():
    user = _User(id="u1", email="op@x.com", name="Op")
    sub = _Sub(user_id="u1", site_id="tokadeh-pilot", channel="email", min_severity="WARNING")
    site = _Site(id="tokadeh-pilot", name="Tokadeh")
    alerts = [_alert(severity="WARNING")]
    key = _digest_key("u1", _now())
    db = _mock_db([(sub, user)], [site], alerts, already_sent_keys=[key])

    digests = await digest_service.build_digests(db, now=_now())
    assert digests == []


@pytest.mark.asyncio
async def test_send_digests_delegates_to_notification_service(monkeypatch):
    user = _User(id="u1", email="op@x.com", name="Op")
    sub = _Sub(user_id="u1", site_id="tokadeh-pilot", channel="email", min_severity="WARNING")
    site = _Site(id="tokadeh-pilot", name="Tokadeh")
    alerts = [_alert(severity="WARNING", id="a1")]
    db = _mock_db([(sub, user)], [site], alerts)

    # Stub audit so we don't need the AuditLog-reading branch inside the
    # mocked execute queue.
    audit_calls = []

    async def _fake_record(_db, **kwargs):
        audit_calls.append(kwargs)
        return MagicMock()

    monkeypatch.setattr(digest_service.audit, "record", _fake_record)

    sent: list[tuple[str, str, str | None]] = []

    class _StubService:
        async def direct(self, *, subject, body, email=None, phone=None):
            sent.append((subject, body, email))

    summary = await digest_service.send_digests(
        db, service=_StubService(), now=_now()
    )
    assert summary == {"sent": 1, "considered": 1}
    assert len(sent) == 1
    subject, _body, email = sent[0]
    assert email == "op@x.com"
    assert "Daily digest" in subject
    assert audit_calls and audit_calls[0]["action"] == "digest_sent"


# --- rank invariants --------------------------------------------------


def test_digest_floor_is_warning():
    assert DIGEST_MIN_RANK == SEVERITY_RANK["WARNING"]
