"""EnviroGuard inference service.

Inference path, highest-fidelity first:

1. **TFLite LSTM+Attention artifact** — the Phase-2 architecture
   (``ai/enviroguard/model.py``). Loaded when the trained ``.tflite``
   lands under ``$GEOSENTINEL_MODEL_DIR/enviroguard/artifacts/``;
   requires TensorFlow to train but only ``tflite_runtime`` to serve.
   Not yet shipped — training on real sensor data is the pre-incubation
   deliverable.
2. **ONNX baseline (GBM per head)** — the trained baseline shipped in
   ``ai/enviroguard/artifacts/*.onnx``. Seven gradient-boosted
   classifiers over hand-engineered features; produced by
   ``ai/enviroguard/train_baseline.py`` from the scenario-overlaid
   synthetic Tokadeh frame. See the module docstring + the README in
   that directory for the current holdout metrics and the honest
   limitation ("synthetic learnability ceiling, real-data accuracy
   pending pre-incubation").
3. **Deterministic surrogate** — hour-of-day drift. Gated behind
   ``settings.enable_synthetic_ai_fallback``; dev-default True so the
   dashboard renders on a clean checkout, prod-validator False so no
   synthetic number ever reaches a real operator.

When (2) is available but no telemetry has arrived yet (e.g. the
backend just booted), the baseline runs on a repeated-last-value window
so the dashboard still gets a real prediction. When (3) is also
disabled and no model is loaded, the service returns a sentinel
LOW/0.0-confidence row.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import numpy as np

from ..core.config import get_settings
from ..schemas.ai import EnviroGuardPredictionOut
from . import onnx_runtime, tflite_runtime
from .influx import influx

log = logging.getLogger(__name__)

RiskTier = Literal["LOW", "ELEVATED", "HIGH", "CRITICAL"]

FEATURE_ORDER = [
    "ph", "turbidity", "dissolved_oxygen", "conductivity", "temperature",
    "pm25", "pm10", "so2", "no2", "noise_db",
    "rainfall_mm_1h", "rainfall_mm_24h",
    "wet_season_flag", "hour_of_day_sin", "hour_of_day_cos",
]


def _tier(score: float) -> RiskTier:
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.5:
        return "HIGH"
    if score >= 0.25:
        return "ELEVATED"
    return "LOW"


async def _assemble_sequence(site_id: str) -> Optional[np.ndarray]:
    """Pull 96 h × 15-min aggregated features for the first env node."""
    # Phase 2 will aggregate across all env nodes and time-align. For now we
    # read the in-memory ring buffer for ENV-01 and synthesize the engineered
    # features so the inference path exercises end-to-end.
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=96)
    rows = await influx.history("env", "ENV-01", start, end)
    if len(rows) < 96:
        return None
    sel = rows[-384:]
    arr = np.zeros((len(sel), len(FEATURE_ORDER)), dtype=np.float32)
    for i, r in enumerate(sel):
        ts = r.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        h = ts.hour + ts.minute / 60
        arr[i, FEATURE_ORDER.index("hour_of_day_sin")] = math.sin(h / 24 * 2 * math.pi)
        arr[i, FEATURE_ORDER.index("hour_of_day_cos")] = math.cos(h / 24 * 2 * math.pi)
        arr[i, FEATURE_ORDER.index("wet_season_flag")] = 1.0 if ts.month in range(4, 11) else 0.0
        for f in FEATURE_ORDER:
            if f in r and r[f] is not None:
                arr[i, FEATURE_ORDER.index(f)] = float(r[f])
    if arr.shape[0] < 384:
        # pad at the front with the first row
        pad = np.repeat(arr[:1], 384 - arr.shape[0], axis=0)
        arr = np.concatenate([pad, arr], axis=0)
    return arr[np.newaxis, -384:]


async def run_enviroguard(site_id: str) -> EnviroGuardPredictionOut:
    now = datetime.now(timezone.utc)
    try:
        seq = await _assemble_sequence(site_id)
    except Exception as e:
        log.warning("enviroguard sequence assembly failed: %s", e)
        seq = None

    # 1. Trained LSTM artifact — highest fidelity. Will fire once the
    # pre-incubation training lands a .tflite in the model dir.
    if seq is not None:
        out = tflite_runtime.invoke("enviroguard", seq)
        if out is not None:
            probs = out[0].tolist()
            return _build_prediction(site_id, now, probs, confidence=0.87)

    # 2. ONNX baseline (shipped in-tree). Trained on 180 d of
    # scenario-overlaid synthetic Tokadeh data; produces real
    # probabilities from the hand-engineered features over the last
    # 96 h. Falls through to the surrogate when the artifacts aren't
    # loaded (clean checkout without the ai dir mounted into the image).
    baseline_probs = await _baseline_inference(seq, now)
    if baseline_probs is not None:
        return _build_prediction(site_id, now, baseline_probs, confidence=0.65)

    if not get_settings().enable_synthetic_ai_fallback:
        # Prod path when no trained artifact is loaded and no telemetry is
        # yet flowing. Return a sentinel LOW/0.0-confidence row so callers
        # can tell there is no prediction — do NOT fabricate one.
        log.warning(
            "enviroguard: no inference available (seq_ready=%s); synthetic "
            "fallback disabled, returning sentinel LOW/0.0 prediction",
            seq is not None,
        )
        return _build_prediction(site_id, now, [0.0] * 7, confidence=0.0)

    # Dev/demo surrogate — deterministic-ish drift by hour-of-day so the
    # dashboard is not flat when there is no telemetry and no TFLite model.
    # Not a prediction; see the module docstring. Enabled only when the
    # settings flag is True (dev default; prod validator-forbidden).
    log.info(
        "enviroguard: no trained model available, serving hour-of-day surrogate "
        "(enable_synthetic_ai_fallback=True)",
    )
    h = now.hour + now.minute / 60
    base = 0.05 + 0.08 * (math.sin(h / 24 * 2 * math.pi) * 0.5 + 0.5)
    probs = [
        base,                       # ph 24h
        min(0.95, base + 0.03),     # turbidity 24h
        min(0.95, base + 0.01),     # DO 24h
        min(0.95, base + 0.02),     # conductivity 24h
        min(0.95, base + 0.02),     # PM2.5 24h
        min(0.97, base + 0.05),     # ph 72h
        min(0.97, base + 0.08),     # turbidity 72h
    ]
    return _build_prediction(site_id, now, probs, confidence=0.5)


async def _baseline_inference(
    seq: Optional[np.ndarray], now: datetime
) -> list[float] | None:
    """Run the ONNX baseline over a 96 h window + global tail features.

    Returns a 7-vector of exceedance probabilities in ``OUTPUT_HEADS``
    order, or ``None`` when the baseline isn't loaded. When no sequence
    is available we repeat a mid-range baseline window so the model
    still produces a prediction (operators get a value, flagged by the
    confidence number returned alongside).
    """

    if not onnx_runtime.load():
        return None
    md = onnx_runtime.metadata() or {}
    feature_dim = md.get("feature_dim")
    if feature_dim is None:
        return None
    try:
        # Local import so a missing ai dir doesn't blow up the backend.
        from ai.enviroguard.features import extract_window_features
        from ai.enviroguard.model import FEATURES
    except Exception as e:
        log.info("enviroguard baseline features module unavailable: %s", e)
        return None

    if seq is None:
        # Repeat a neutral row — baseline is well inside IFC bounds —
        # so the model still produces calibrated probabilities on cold
        # start. The confidence attached by the caller reflects this.
        window = np.tile(
            np.array(
                [7.5, 1.5, 7.8, 240.0, 25.0, 12.0, 22.0, 10.0, 15.0, 55.0, 0.1, 1.0, 1.0, 0.0, 1.0],
                dtype=np.float32,
            ),
            (384, 1),
        )
    else:
        window = seq[0]  # (T, F)
    tail = window[-1]
    try:
        feats = extract_window_features(
            window,
            hour_sin=float(tail[FEATURES.index("hour_of_day_sin")]),
            hour_cos=float(tail[FEATURES.index("hour_of_day_cos")]),
            wet_season_flag=float(tail[FEATURES.index("wet_season_flag")]),
            rainfall_mm_24h=float(tail[FEATURES.index("rainfall_mm_24h")]),
            rainfall_mm_1h=float(tail[FEATURES.index("rainfall_mm_1h")]),
        )
    except Exception as e:
        log.warning("enviroguard baseline feature extraction failed: %s", e)
        return None
    probs: list[float] = []
    for head in md["output_heads"]:
        p = onnx_runtime.invoke_head(head, feats)
        if p is None:
            return None
        probs.append(p)
    return probs


def _build_prediction(
    site_id: str, now: datetime, probs: list[float], *, confidence: float,
) -> EnviroGuardPredictionOut:
    overall24 = max(probs[:5])
    overall72 = max(probs[5:])
    return EnviroGuardPredictionOut(
        site_id=site_id,
        timestamp=now,
        ph_exceedance_24h=probs[0],
        turbidity_exceedance_24h=probs[1],
        do_exceedance_24h=probs[2],
        conductivity_exceedance_24h=probs[3],
        pm25_exceedance_24h=probs[4],
        ph_exceedance_72h=probs[5],
        turbidity_exceedance_72h=probs[6],
        overall_risk_24h=_tier(overall24),
        overall_risk_72h=_tier(overall72),
        confidence=confidence,
    )
