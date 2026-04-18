"""Training-label store (Phase 2.4 §1).

Labels for supervised training of EnviroGuard / SlopeWatch. Each row marks
an observed or inferred positive event (e.g. water-quality breach, slope
creep). ``source`` records provenance so synthetic augmentation is flagged
explicitly — the evaluation harness must be able to restrict to real labels.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class TrainingLabel(Base):
    __tablename__ = "training_labels"
    __table_args__ = (
        Index("ix_training_labels_site_param", "site_id", "parameter"),
        Index("ix_training_labels_window", "t_start", "t_end"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(64), index=True)
    parameter: Mapped[str] = mapped_column(String(64))
    t_start: Mapped[datetime] = mapped_column(DateTime)
    t_end: Mapped[datetime] = mapped_column(DateTime)
    # Label is a free-form string so EnviroGuard (``exceedance``) and
    # SlopeWatch (``creep`` / ``failure``) can share the table.
    label: Mapped[str] = mapped_column(String(64))
    # ``field``, ``ifc_report``, ``insar``, ``synthetic`` — the evaluation
    # harness filters on this to keep metrics honest.
    source: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
