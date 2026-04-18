"""InSAR API payloads (Phase 3 §InSAR time series).

Shape consumed by the Operations dashboard's cumulative-displacement
chart and velocity badge.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InsarPoint(BaseModel):
    timestamp: datetime
    displacement_mm: float = Field(
        description="Cumulative line-of-sight displacement vs. the master scene (mm)",
    )


class InsarSeries(BaseModel):
    site_id: str
    slope_id: str
    points: list[InsarPoint]
    velocity_mm_yr: float | None = Field(
        None,
        description="Linear-fit velocity across the window; null when no points ingested yet",
    )
    window_days: int = Field(90, ge=7, le=365)
