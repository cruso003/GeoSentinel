"""EnviroGuard inference service.

Phase 1: deterministic synthetic predictor producing outputs in the same schema
as the LSTM+Attention model (Spec §13.1). Phase 2: load TFLite model and run
inference on the last 96h of InfluxDB-sourced sensor data.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal

from ..schemas.ai import EnviroGuardPredictionOut


RiskTier = Literal["LOW", "ELEVATED", "HIGH", "CRITICAL"]


def _tier(score: float) -> RiskTier:
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.5:
        return "HIGH"
    if score >= 0.25:
        return "ELEVATED"
    return "LOW"


async def run_enviroguard(site_id: str) -> EnviroGuardPredictionOut:
    """Return a prediction. In Phase 1 this is deterministic-ish from time-of-day.

    A real implementation would:
      1. Query InfluxDB for 96h of sensor data (all env nodes).
      2. Interpolate missing values (forward fill, max 6 steps).
      3. Normalise using the stored scaler.
      4. Run TFLite inference.
      5. Map outputs to EnviroGuardPrediction schema.
      6. Persist + push to WebSocket subscribers.
    """
    now = datetime.now(timezone.utc)
    # Small diurnal drift so predictions aren't flat in dev.
    h = now.hour + now.minute / 60
    base = 0.05 + 0.08 * (math.sin(h / 24 * 2 * math.pi) * 0.5 + 0.5)
    cond24 = min(0.95, base + 0.02)
    turb24 = min(0.95, base + 0.03)
    ph24 = min(0.95, base)
    do24 = min(0.95, base + 0.01)
    pm25_24 = min(0.95, base + 0.02)
    overall24 = max(cond24, ph24, turb24, do24, pm25_24)
    overall72 = min(0.97, overall24 + 0.05)
    return EnviroGuardPredictionOut(
        site_id=site_id,
        timestamp=now,
        ph_exceedance_24h=ph24,
        turbidity_exceedance_24h=turb24,
        do_exceedance_24h=do24,
        conductivity_exceedance_24h=cond24,
        pm25_exceedance_24h=pm25_24,
        ph_exceedance_72h=min(0.97, ph24 + 0.05),
        turbidity_exceedance_72h=min(0.97, turb24 + 0.05),
        overall_risk_24h=_tier(overall24),
        overall_risk_72h=_tier(overall72),
        confidence=0.82,
    )
