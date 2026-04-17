"""CRITICAL / EVACUATION alert dispatch (Spec §8.5).

- Email via SMTP (aiosmtplib when installed, stdlib fallback)
- SMS via Twilio REST API (httpx)
- Logs when no provider is configured so dev still exercises the code path.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Iterable, Optional

import httpx

from ..core.config import get_settings

log = logging.getLogger(__name__)


class NotificationService:
    async def dispatch(self, *, site_id: str, severity: str, message: str) -> None:
        settings = get_settings()
        subject = f"[GeoSentinel {severity}] {site_id}"
        recipients = self._recipients_for_site(site_id)

        await self._send_email(
            settings=settings,
            subject=subject,
            body=message,
            to=[e for e, _ in recipients if e],
        )
        await self._send_sms(
            settings=settings,
            body=f"{subject}: {message}"[:320],
            to=[p for _, p in recipients if p],
        )

    def _recipients_for_site(self, site_id: str) -> Iterable[tuple[Optional[str], Optional[str]]]:
        # Phase 2 replacement: query users/subscriptions table per site.
        # For now, return an empty iterable; CRITICAL alerts are logged and
        # still broadcast over WebSocket to the control room.
        return []

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
