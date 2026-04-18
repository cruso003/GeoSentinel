"""CRITICAL / EVACUATION alert dispatch (Spec §8.5).

- Email via SMTP (aiosmtplib when installed, stdlib fallback).
- SMS via Twilio REST API (httpx).
- Phase 2.3: recipients resolved from ``notification_subscriptions`` — each
  row ties a user to a (site, channel, min_severity). Users with the matching
  channel + a ``min_severity`` no stronger than the incoming severity are
  notified. Missing provider credentials degrade to structured logs so dev
  still exercises the code path.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import httpx
from sqlalchemy import select

from ..core.config import get_settings
from ..core.db import SessionLocal
from ..models.notifications import NotificationSubscription
from ..models.user import User

log = logging.getLogger(__name__)


# Severity is a four-tier ladder; "covered by min_severity ≤ incoming" means
# comparing their positions. INFO is the weakest, EVACUATION the strongest.
SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2, "EVACUATION": 3}


def _rank(sev: str) -> int:
    return SEVERITY_RANK.get(sev, 0)


class NotificationService:
    def _has_sms_provider(self) -> bool:
        """True when Twilio creds are fully configured. The community
        opt-in flow uses this to decide whether to expose the dev-only
        debug code in its response (safe only when ``direct`` is a noop)."""
        settings = get_settings()
        return bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
        )

    async def direct(
        self,
        *,
        subject: str,
        body: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> None:
        """Send to a specific recipient without consulting subscriptions.

        Used for escalation hops and the operator test-alert button where the
        target is chosen explicitly. Missing provider creds degrade to logs.
        """
        settings = get_settings()
        await self._send_email(
            settings=settings,
            subject=subject,
            body=body,
            to=[email] if email else [],
        )
        await self._send_sms(
            settings=settings,
            body=f"{subject}: {body}"[:320],
            to=[phone] if phone else [],
        )

    async def dispatch(self, *, site_id: str, severity: str, message: str) -> None:
        settings = get_settings()
        subject = f"[GeoSentinel {severity}] {site_id}"
        recipients = await self._recipients_for_site(site_id=site_id, severity=severity)

        emails = sorted({e for e, _ in recipients if e})
        phones = sorted({p for _, p in recipients if p})

        await self._send_email(
            settings=settings,
            subject=subject,
            body=message,
            to=emails,
        )
        await self._send_sms(
            settings=settings,
            body=f"{subject}: {message}"[:320],
            to=phones,
        )

    async def _recipients_for_site(
        self, *, site_id: str, severity: str
    ) -> list[tuple[str | None, str | None]]:
        """Return ``(email, phone)`` pairs for each active subscription whose
        ``min_severity`` rank is ≤ the incoming severity. A user who opts into
        email receives an ``(email, None)`` row; an opt-in for SMS returns
        ``(None, phone)``. The caller dedupes across channels."""

        incoming = _rank(severity)
        rows: list[tuple[str | None, str | None]] = []
        async with SessionLocal() as db:
            stmt = (
                select(NotificationSubscription, User)
                .join(User, User.id == NotificationSubscription.user_id)
                .where(
                    NotificationSubscription.site_id == site_id,
                    NotificationSubscription.active.is_(True),
                )
            )
            result = (await db.execute(stmt)).all()

        for sub, user in result:
            if _rank(sub.min_severity) > incoming:
                continue
            if sub.channel == "email":
                rows.append((user.email, None))
            elif sub.channel == "sms" and user.phone_number:
                rows.append((None, user.phone_number))
            # push is a future channel — no-op for now, logged by dispatch.
        return rows

    async def _send_email(self, settings, *, subject: str, body: str, to: list[str]) -> None:
        if not settings.smtp_host or not to:
            log.info("notifications.email[noop]: subject=%s, recipients=%s", subject, to)
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user or "geosentinel@localhost"
        msg["To"] = ", ".join(to)
        msg.set_content(body)
        try:
            import aiosmtplib  # type: ignore

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=bool(settings.smtp_user),
            )
        except ImportError:  # pragma: no cover
            import smtplib

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
                if settings.smtp_user:
                    s.starttls()
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        except Exception as e:  # pragma: no cover - dev SMTP often unavailable
            log.warning("notifications.email failed: %s", e)

    async def _send_sms(self, settings, *, body: str, to: list[str]) -> None:
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
            if to:
                log.info("notifications.sms[noop]: %s -> %s", body, to)
            return
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            for number in to:
                try:
                    await client.post(
                        url,
                        data={"From": settings.twilio_from_number, "To": number, "Body": body},
                        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                    )
                except Exception as e:  # pragma: no cover
                    log.warning("notifications.sms failed for %s: %s", number, e)


notifications = NotificationService()


def validate_e164(phone: str | None) -> str | None:
    """Return the phone if it's a valid E.164 string (``+`` + 8-15 digits),
    else ``None``. Used by the profile API and seed loader."""
    if not phone:
        return None
    phone = phone.strip()
    if not phone.startswith("+"):
        return None
    digits = phone[1:]
    if not digits.isdigit():
        return None
    if not (8 <= len(digits) <= 15):
        return None
    return phone
