"""Training-label schemas (Phase 2.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LABEL_SOURCES = Literal["field", "ifc_report", "insar", "synthetic"]


class TrainingLabelIn(BaseModel):
    site_id: str
    node_id: str
    parameter: str = Field(max_length=64)
    t_start: datetime
    t_end: datetime
    label: str = Field(max_length=64)
    source: LABEL_SOURCES
    notes: str | None = None

    @field_validator("t_end")
    @classmethod
    def _window(cls, v: datetime, info):
        start = info.data.get("t_start")
        if start is not None and v <= start:
            raise ValueError("t_end must be after t_start")
        return v


class TrainingLabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    node_id: str
    parameter: str
    t_start: datetime
    t_end: datetime
    label: str
    source: str
    notes: str | None
    created_at: datetime
