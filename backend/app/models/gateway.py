"""Per-gateway credentials (Phase 2.1 §7).

Each field gateway gets a row with a hashed API key and an optional
`allowed_node_ids` allow-list. `/sensors/ingest` looks up the presented
key, verifies its hash, and rejects readings for nodes outside the scope.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class SensorGateway(Base):
    __tablename__ = "sensor_gateways"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    hashed_key: Mapped[str] = mapped_column(String(255))
    allowed_node_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
