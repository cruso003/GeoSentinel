from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"))
    report_type: Mapped[str] = mapped_column(String(32))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|generating|ready|failed
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_integrity_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
