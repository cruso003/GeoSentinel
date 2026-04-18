"""SlopeWatch PINN inference service.

Phase 2: loads the trained TFLite PINN and runs it on the last 72 h of geo
telemetry per slope. Phase 1 fallback: blends Mohr-Coulomb FoS with a
deterministic stability baseline.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

import numpy as np

from ..schemas.ai import SlopeWatchPredictionOut
from . import tflite_runtime
from .influx import influx
from .insar_ingest import latest_velocity_mm_yr, velocity_to_factor

log = logging.getLogger(__name__)

SlopeAlertTier = Literal["NORMAL", "WATCH", "WARNING", "CRITICAL", "EVACUATION"]

FEATURE_ORDER = [
    "tilt_x", "tilt_y", "crack_displacement", "pore_pressure",
    "seismic_magnitude", "rainfall_mm_1h", "rainfall_mm_24h",
    "insar_displacement_mm", "slope_height_m", "slope_angle_deg",
]

SEQ_LEN = 288  # 72 h @ 15 min


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


def _fos_fallback(geo_row: dict | None) -> float:
    """Compute a baseline risk via Mohr-Coulomb when no TFLite + no history."""
    try:
        from ai.slopewatch.physics.mohr_coulomb import Slice, Soil, factor_of_safety, risk_from_fos
    except Exception:
        return 0.18
    u = float((geo_row or {}).get("pore_pressure") or 25.0)
    slices = [Slice(weight=200 + 20 * i, base_angle_deg=45 - 12 * i, base_length=3.5, pore_pressure=u) for i in range(6)]
    try:
        fos = factor_of_safety(slices, Soil(cohesion=15, friction_angle_deg=32))
    except Exception:
        return 0.18
    return risk_from_fos(fos)


async def _assemble_sequence(site_id: str, slope_id: str) -> Optional[np.ndarray]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=72)
    rows = await influx.history("geo", slope_id, start, end)
    if len(rows) < 48:
        return None
    sel = rows[-SEQ_LEN:]
    arr = np.zeros((len(sel), len(FEATURE_ORDER)), dtype=np.float32)
    for i, r in enumerate(sel):
        for f in FEATURE_ORDER:
            if f in r and r[f] is not None:
                arr[i, FEATURE_ORDER.index(f)] = float(r[f])
    if arr.shape[0] < SEQ_LEN:
        pad = np.repeat(arr[:1], SEQ_LEN - arr.shape[0], axis=0)
        arr = np.concatenate([pad, arr], axis=0)
    return arr[np.newaxis, -SEQ_LEN:]


async def run_slopewatch(site_id: str, slope_ids: List[str]) -> List[SlopeWatchPredictionOut]:
    now = datetime.now(timezone.utc)
    out: List[SlopeWatchPredictionOut] = []
    for slope_id in slope_ids:
        score: Optional[float] = None
        try:
            seq = await _assemble_sequence(site_id, slope_id)
            if seq is not None:
                inf = tflite_runtime.invoke("slopewatch", seq)
                if inf is not None:
                    score = float(inf[0].flatten()[0])
        except Exception as e:
            log.warning("slopewatch inference error for %s: %s", slope_id, e)

        if score is None:
            latest = await influx.latest("geo", slope_id)
            score = _fos_fallback(latest)

        # Factor decomposition: pore / tilt / rainfall track the risk
        # score linearly (Phase-2 approximation). ``insar_factor`` is
        # pulled from the latest InSAR velocity via the calibrated
        # ladder in ``insar_ingest``; when no InSAR series is ingested
        # yet we fall back to the old 0.15 * score weighting so the PDF
        # + dashboard still get a plausible bar.
        pore = 0.35 * score
        tilt = 0.25 * score
        velocity = await latest_velocity_mm_yr(slope_id)
        insar = velocity_to_factor(velocity) if velocity is not None else 0.15 * score
        rain = max(0.0, min(1.0, score - pore - tilt - insar))

        out.append(SlopeWatchPredictionOut(
            site_id=site_id,
            slope_id=slope_id,
            timestamp=now,
            risk_score=score,
            alert_tier=_tier(score),
            pore_pressure_factor=round(pore, 3),
            tilt_factor=round(tilt, 3),
            insar_factor=round(insar, 3),
            rainfall_factor=round(rain, 3),
            trend="STABLE" if score < 0.3 else "DETERIORATING",
            trend_rate=round(max(0.0, score - 0.3), 3),
        ))
    return out
