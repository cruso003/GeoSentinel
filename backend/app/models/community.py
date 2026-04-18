"""Community opt-in pending rows (Phase 2.3 §Community).

A resident submits phone + site → we generate a 6-digit code, store only
its SHA-256 hash here, and send the plaintext via SMS. The row stays
until either (a) confirmation converts it into a real user + subscription,
or (b) ``expires_at`` has passed.

Uniqueness on ``(phone_number, site_id)`` means re-requesting the code
replaces the pending row — the caller never accumulates stale codes.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CommunityOptIn(Base):
    __tablename__ = "community_opt_ins"
    __table_args__ = (
        UniqueConstraint(
            "phone_number", "site_id", name="uq_community_opt_in_phone_site"
        ),
        Index(
            "ix_community_opt_in_phone_site_expires",
            "phone_number",
            "site_id",
            "expires_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    phone_number: Mapped[str] = mapped_column(String(20))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"))
    language: Mapped[str] = mapped_column(String(8), default="en")
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
