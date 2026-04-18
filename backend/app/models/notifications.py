"""Phase 2.3 — notification preferences + per-site RBAC.

Three tables live here:

- ``notification_subscription`` — a user's opt-in to receive alerts at or
  above ``min_severity`` for one site via one channel.
- ``user_site`` — explicit membership. Replaces the implicit "any user with
  role X can see any site" model.
- ``escalation_step`` — ordered responder chain per site. Unacked CRITICAL /
  EVACUATION alerts walk this ladder with a 5-minute dwell per hop.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "site_id", "channel", name="uq_notification_sub_user_site_channel"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))  # email | sms | push
    min_severity: Mapped[str] = mapped_column(String(16), default="CRITICAL")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSite(Base):
    __tablename__ = "user_sites"
    __table_args__ = (
        UniqueConstraint("user_id", "site_id", name="uq_user_site_user_site"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # operator | esg_admin | community
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EscalationStep(Base):
    """Per-site responder ladder. ``position`` is the 0-indexed hop order."""

    __tablename__ = "escalation_steps"
    __table_args__ = (
        UniqueConstraint("site_id", "position", name="uq_escalation_site_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
