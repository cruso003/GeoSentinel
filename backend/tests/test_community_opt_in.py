"""Community SMS opt-in flow (Phase 2.3 §Community).

The service layer is exercised with a mocked AsyncSession that returns
fixed rows for each ``execute()`` call, plus a stub NotificationService
to capture SMS payloads. Pure validation + code-hashing behaviour gets
unit coverage alongside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import community_opt_in as optin
from app.services.community_opt_in import (
    CODE_LENGTH,
    CODE_TTL,
    MAX_ATTEMPTS,
    OptInError,
    _ensure_language,
    _generate_code,
    _hash_code,
    confirm_opt_in,
    request_opt_in,
)


# --- pure helpers -----------------------------------------------------


def test_generate_code_length_and_digits():
    for _ in range(20):
        code = _generate_code()
        assert len(code) == CODE_LENGTH
        assert code.isdigit()


def test_hash_code_is_stable_and_not_plaintext():
    h = _hash_code("123456")
    assert h != "123456"
    assert len(h) == 64  # SHA-256 hex
    assert _hash_code("123456") == h


def test_ensure_language_unknown_falls_back_to_english():
    assert _ensure_language("klingon") == "en"
    assert _ensure_language("") == "en"
    assert _ensure_language("MANO") == "mano"
    assert _ensure_language("gio") == "gio"


def test_ttl_and_attempts_constants():
    assert CODE_TTL == timedelta(minutes=10)
    assert MAX_ATTEMPTS == 5
    assert CODE_LENGTH == 6


# --- fakes ------------------------------------------------------------


@dataclass
class _Pending:
    id: str = "p1"
    phone_number: str = "+231881234567"
    site_id: str = "tokadeh-pilot"
    language: str = "en"
    code_hash: str = field(default_factory=lambda: _hash_code("000000"))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + CODE_TTL)
    attempts: int = 0
    confirmed_at: datetime | None = None


@dataclass
class _User:
    id: str = "u1"
    email: str = "sms-231881234567@community.geosentinel.local"
    name: str = "Community · +231881234567"
    phone_number: str | None = "+231881234567"
    role: str = "community"
    hashed_password: str = ""


@dataclass
class _Sub:
    id: str = "s1"
    user_id: str = "u1"
    site_id: str = "tokadeh-pilot"
    channel: str = "sms"
    min_severity: str = "CRITICAL"
    active: bool = True


def _scalar(value):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=value)
    return r


class _StubNotifications:
    def __init__(self, *, has_sms: bool = False):
        self._has_sms = has_sms
        self.sent: list[dict] = []

    def _has_sms_provider(self) -> bool:
        return self._has_sms

    async def direct(self, *, subject, body, email=None, phone=None):
        self.sent.append({"subject": subject, "body": body, "phone": phone})


def _mock_db(execute_returns):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute_returns)
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# --- request_opt_in ---------------------------------------------------


@pytest.mark.asyncio
async def test_request_opt_in_rejects_bad_phone():
    service = _StubNotifications()
    db = _mock_db([])
    with pytest.raises(OptInError):
        await request_opt_in(
            db, phone="123", site_id="tokadeh-pilot", service=service
        )


@pytest.mark.asyncio
async def test_request_opt_in_creates_pending_when_absent():
    # First execute = select existing → None
    db = _mock_db([_scalar(None)])
    service = _StubNotifications(has_sms=False)  # dev → exposes debug_code
    now = datetime(2026, 4, 18, 7, 0, tzinfo=UTC)

    result = await optin.request_opt_in(
        db,
        phone="+231881234567",
        site_id="tokadeh-pilot",
        language="mano",
        service=service,
        now=now,
    )

    # New pending row added; SMS sent; debug_code leaked (no provider).
    assert db.add.called
    pending = db.add.call_args.args[0]
    assert pending.language == "mano"
    assert pending.attempts == 0
    assert pending.expires_at == now + CODE_TTL
    assert result.expires_at == now + CODE_TTL
    assert result.debug_code is not None
    assert _hash_code(result.debug_code) == pending.code_hash
    assert service.sent and service.sent[0]["phone"] == "+231881234567"


@pytest.mark.asyncio
async def test_request_opt_in_replaces_existing_and_resets_attempts():
    existing = _Pending(
        code_hash=_hash_code("999999"),
        attempts=4,
        language="en",
    )
    db = _mock_db([_scalar(existing)])
    service = _StubNotifications(has_sms=True)  # production → hide debug_code
    now = datetime(2026, 4, 18, 7, 0, tzinfo=UTC)

    result = await optin.request_opt_in(
        db,
        phone="+231881234567",
        site_id="tokadeh-pilot",
        language="gio",
        service=service,
        now=now,
    )
    assert existing.attempts == 0
    assert existing.expires_at == now + CODE_TTL
    assert existing.language == "gio"
    assert existing.code_hash != _hash_code("999999")
    assert result.debug_code is None


@pytest.mark.asyncio
async def test_request_opt_in_is_noop_when_already_confirmed():
    confirmed = _Pending(confirmed_at=datetime.now(UTC))
    db = _mock_db([_scalar(confirmed)])
    service = _StubNotifications()
    result = await optin.request_opt_in(
        db,
        phone="+231881234567",
        site_id="tokadeh-pilot",
        service=service,
    )
    assert result.debug_code is None
    assert service.sent == []
    # No new row or mutation
    assert not db.add.called


# --- confirm_opt_in ---------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_opt_in_rejects_non_numeric_code():
    db = _mock_db([])
    with pytest.raises(OptInError):
        await confirm_opt_in(
            db, phone="+231881234567", site_id="tokadeh-pilot", code="abcdef"
        )


@pytest.mark.asyncio
async def test_confirm_opt_in_rejects_expired_code():
    past = _Pending(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    db = _mock_db([_scalar(past)])
    with pytest.raises(OptInError, match="expired"):
        await confirm_opt_in(
            db, phone="+231881234567", site_id="tokadeh-pilot", code="000000"
        )


@pytest.mark.asyncio
async def test_confirm_opt_in_rejects_after_max_attempts():
    pending = _Pending(attempts=MAX_ATTEMPTS)
    db = _mock_db([_scalar(pending)])
    with pytest.raises(OptInError, match="too many"):
        await confirm_opt_in(
            db, phone="+231881234567", site_id="tokadeh-pilot", code="000000"
        )


@pytest.mark.asyncio
async def test_confirm_opt_in_rejects_wrong_code_and_increments_attempts():
    pending = _Pending(code_hash=_hash_code("123456"), attempts=0)
    db = _mock_db([_scalar(pending)])
    with pytest.raises(OptInError, match="incorrect"):
        await confirm_opt_in(
            db, phone="+231881234567", site_id="tokadeh-pilot", code="000000"
        )
    assert pending.attempts == 1


@pytest.mark.asyncio
async def test_confirm_opt_in_happy_path_new_user():
    pending = _Pending(code_hash=_hash_code("424242"))
    # Sequence the service does in the happy path:
    # 1) select pending
    # 2) select existing user by phone → None (new)
    # 3) select existing user_site → None
    # 4) select existing subscription → None
    # 5) delete pending
    delete_result = MagicMock()
    db = _mock_db(
        [
            _scalar(pending),
            _scalar(None),
            _scalar(None),
            _scalar(None),
            delete_result,
        ]
    )

    result = await confirm_opt_in(
        db,
        phone="+231881234567",
        site_id="tokadeh-pilot",
        code="424242",
    )
    assert result.user_id
    assert result.subscription_id
    # 3 db.add calls: User, UserSite, Subscription
    assert db.add.call_count == 3
    types_added = [type(c.args[0]).__name__ for c in db.add.call_args_list]
    assert "User" in types_added
    assert "UserSite" in types_added
    assert "NotificationSubscription" in types_added
    assert pending.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_opt_in_reuses_existing_user_and_subscription():
    pending = _Pending(code_hash=_hash_code("101010"))
    user = _User()
    membership = MagicMock()
    existing_sub = _Sub(active=False)

    db = _mock_db(
        [
            _scalar(pending),
            _scalar(user),
            _scalar(membership),
            _scalar(existing_sub),
            MagicMock(),  # delete
        ]
    )

    result = await confirm_opt_in(
        db,
        phone="+231881234567",
        site_id="tokadeh-pilot",
        code="101010",
    )
    assert result.user_id == user.id
    assert result.subscription_id == existing_sub.id
    assert existing_sub.active is True
    # No new User / UserSite / Subscription created
    assert not db.add.called
