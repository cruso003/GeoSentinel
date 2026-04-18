"""Community SMS opt-in flow (Phase 2.3 §Community).

Two steps, both on public endpoints:

1. ``request_opt_in(db, phone, site_id, language)`` — generate a 6-digit
   code, store only its SHA-256 hash + expiry, then send the plaintext
   over SMS via :class:`NotificationService.direct`. The caller never
   sees the code; only their phone does.
2. ``confirm_opt_in(db, phone, site_id, code)`` — validate the code in
   constant time against the pending row. Successful confirmation
   provisions (or locates) a ``community``-role user and writes an
   active SMS ``notification_subscription`` so they start receiving
   CRITICAL / EVACUATION pages + local-language templates.

The flow is deliberately self-contained: no external verification
provider (Twilio Verify is a Phase 3 upgrade). The pending row caps
attempts at :data:`MAX_ATTEMPTS`; re-requesting the code before
expiry overwrites the hash and resets the counter.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.community import CommunityOptIn
from ..models.notifications import NotificationSubscription, UserSite
from ..models.user import User
from .notifications import NotificationService, validate_e164
from .notifications_templates import AVAILABLE_LANGUAGES, render

log = logging.getLogger(__name__)


CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
CODE_LENGTH = 6


class OptInError(ValueError):
    """Raised for user-visible problems: bad phone, bad code, exhausted
    attempts. The API layer maps this to 400; the ``reason`` is the client
    message."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RequestResult:
    phone_number: str
    site_id: str
    expires_at: datetime
    # Dev-only: None in production, set when the notification backend is
    # noop so smoke-tests can still drive the flow.
    debug_code: str | None = None


@dataclass(frozen=True)
class ConfirmResult:
    user_id: str
    subscription_id: str


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    # Zero-padded so leading zeros survive "send as string".
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def _ensure_language(language: str) -> str:
    lang = (language or "en").strip().lower()
    if lang not in AVAILABLE_LANGUAGES:
        lang = "en"
    return lang


async def request_opt_in(
    db: AsyncSession,
    *,
    phone: str,
    site_id: str,
    language: str = "en",
    service: NotificationService,
    now: datetime | None = None,
) -> RequestResult:
    """Start a pending opt-in. Upserts on (phone, site_id) so a resident
    who doesn't receive the first SMS can re-request without a reset tool.
    """

    phone_norm = validate_e164(phone)
    if phone_norm is None:
        raise OptInError("phone_number must be E.164 (e.g. +231881234567)")
    lang = _ensure_language(language)
    now = now or datetime.now(UTC)

    existing = (
        await db.execute(
            select(CommunityOptIn).where(
                CommunityOptIn.phone_number == phone_norm,
                CommunityOptIn.site_id == site_id,
            )
        )
    ).scalar_one_or_none()

    code = _generate_code()
    expires_at = now + CODE_TTL
    code_hash = _hash_code(code)

    if existing is not None:
        if existing.confirmed_at is not None:
            # Already confirmed — treat as success without issuing a new
            # code. Prevents an attacker re-harvesting SMS for a known pair.
            return RequestResult(
                phone_number=phone_norm, site_id=site_id, expires_at=now
            )
        existing.language = lang
        existing.code_hash = code_hash
        existing.expires_at = expires_at
        existing.attempts = 0
    else:
        db.add(
            CommunityOptIn(
                id=str(uuid4()),
                phone_number=phone_norm,
                site_id=site_id,
                language=lang,
                code_hash=code_hash,
                expires_at=expires_at,
                attempts=0,
            )
        )
    await db.flush()

    sms_body = render(
        language=lang,
        key="community_confirm",
        site=site_id,
        code=code,
    )
    await service.direct(subject="GeoSentinel opt-in", body=sms_body, phone=phone_norm)
    await db.commit()

    # The notification backend is a no-op in dev — expose the code so
    # smoke-tests can complete the flow. Never leaks in prod where
    # Twilio creds are present (service.direct actually delivers).
    debug_code = None
    if not getattr(service, "_has_sms_provider", lambda: False)():
        debug_code = code

    return RequestResult(
        phone_number=phone_norm,
        site_id=site_id,
        expires_at=expires_at,
        debug_code=debug_code,
    )


async def confirm_opt_in(
    db: AsyncSession,
    *,
    phone: str,
    site_id: str,
    code: str,
    now: datetime | None = None,
) -> ConfirmResult:
    """Redeem a pending code. On success, provisions (or reuses) a
    community-role user, adds a ``user_sites`` row, and writes an active
    SMS subscription with ``min_severity=CRITICAL``."""

    phone_norm = validate_e164(phone)
    if phone_norm is None:
        raise OptInError("phone_number must be E.164 (e.g. +231881234567)")
    if not code or not code.isdigit() or len(code) != CODE_LENGTH:
        raise OptInError("confirmation code must be 6 digits")
    now = now or datetime.now(UTC)

    pending = (
        await db.execute(
            select(CommunityOptIn).where(
                CommunityOptIn.phone_number == phone_norm,
                CommunityOptIn.site_id == site_id,
            )
        )
    ).scalar_one_or_none()
    if pending is None or pending.confirmed_at is not None:
        raise OptInError("no pending confirmation for that phone + site")
    if now > pending.expires_at:
        raise OptInError("confirmation code expired; request a new one")
    if pending.attempts >= MAX_ATTEMPTS:
        raise OptInError("too many attempts; request a new code")

    pending.attempts += 1
    if not hmac.compare_digest(pending.code_hash, _hash_code(code)):
        await db.commit()
        raise OptInError("incorrect confirmation code")

    pending.confirmed_at = now

    user = (
        await db.execute(select(User).where(User.phone_number == phone_norm))
    ).scalar_one_or_none()
    if user is None:
        # Synthesise a unique placeholder email. Community users log in
        # via the phone (future PWA) — the email slot just needs to be
        # unique + parseable.
        placeholder_email = f"sms-{phone_norm.lstrip('+')}@community.geosentinel.local"
        user = User(
            id=str(uuid4()),
            email=placeholder_email,
            name=f"Community · {phone_norm}",
            hashed_password="",  # no password auth for SMS-only users
            role="community",
            phone_number=phone_norm,
        )
        db.add(user)
        await db.flush()

    membership = (
        await db.execute(
            select(UserSite).where(
                UserSite.user_id == user.id, UserSite.site_id == site_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(
            UserSite(
                id=str(uuid4()),
                user_id=user.id,
                site_id=site_id,
                role="community",
            )
        )

    # Upsert the SMS subscription. A returning user who re-confirms keeps
    # their existing subscription (with whatever min_severity they had).
    sub = (
        await db.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.user_id == user.id,
                NotificationSubscription.site_id == site_id,
                NotificationSubscription.channel == "sms",
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = NotificationSubscription(
            id=str(uuid4()),
            user_id=user.id,
            site_id=site_id,
            channel="sms",
            min_severity="CRITICAL",
            active=True,
        )
        db.add(sub)
    else:
        sub.active = True
    await db.flush()

    # Once redeemed, the pending row is consumed — deleting keeps the
    # table bounded.
    await db.execute(
        delete(CommunityOptIn).where(CommunityOptIn.id == pending.id)
    )
    await db.commit()

    log.info(
        "community.opt_in confirmed phone=%s site=%s user_id=%s",
        phone_norm,
        site_id,
        user.id,
    )
    return ConfirmResult(user_id=user.id, subscription_id=sub.id)
