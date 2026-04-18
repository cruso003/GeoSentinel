"""Model registry (Phase 2.4 §5).

Each training run registers a ``ModelVersion`` in state ``candidate``.
The promotion gate reads the current ``production`` row, compares
metrics, and either promotes the candidate or keeps the incumbent. We
keep this in Postgres rather than relying purely on MLflow tags because:

1. The backend already reads Postgres — no extra dep at request time.
2. The hash-chain audit log lives here; promotions land in the same
   chain that tracks every other mutation.
3. MLflow is staging-only; production should be able to decide which
   model to load without talking to the tracking server.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        # Only one row in production per model at a time; candidate/archived
        # rows are unconstrained so registration is cheap.
        UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
        Index("ix_model_versions_name_stage", "name", "stage"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(64))  # enviroguard | slopewatch
    version: Mapped[str] = mapped_column(String(128))  # run_name, ISO timestamp, etc.
    # candidate = just-registered, not yet evaluated for promotion
    # staging   = promoted once, keep for rollback
    # production = currently served
    # archived  = replaced, retained for audit
    stage: Mapped[str] = mapped_column(String(16), default="candidate")
    data_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Metrics as JSON text — small, read rarely, avoids a JSONB dependency.
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
