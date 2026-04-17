"""SlopeWatch PINN inference service.

Phase 1: deterministic synthetic per-slope score. Phase 2: Keras PINN with
Mohr-Coulomb physics constraint layer (Spec §13.2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal

from ..schemas.ai import SlopeWatchPredictionOut


SlopeAlertTier = Literal["NORMAL", "WATCH", "WARNING", "CRITICAL", "EVACUATION"]


def _tier(score: float) -> SlopeAlertTier:
    if score >= 0.85:
        return "EVACUATION"
    if score >= 0.7:
        return "CRITICAL"
    if score >= 0.45:
        return "WARNING"
    if score >= 0.25:
        return "WATCH"
    return "NORMAL"


async def run_slopewatch(site_id: str, slope_ids: List[str]) -> List[SlopeWatchPredictionOut]:
    now = datetime.now(timezone.utc)
    out: List[SlopeWatchPredictionOut] = []
    for sid in slope_ids:
        # Stable low-risk baseline in Phase 1; the mock front-end drives
        # scenarios. Backend deterministic output used only when real data
        # unavailable.
        score = 0.18
        out.append(
            SlopeWatchPredictionOut(
                site_id=site_id,
                slope_id=sid,
                timestamp=now,
                risk_score=score,
                alert_tier=_tier(score),
                pore_pressure_factor=0.22,
                tilt_factor=0.15,
                insar_factor=0.1,
                rainfall_factor=0.12,
                trend="STABLE",
                trend_rate=0.0,
            )
        )
    return out
