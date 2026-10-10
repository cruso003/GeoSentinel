"""Feature engineering for the EnviroGuard baseline classifier.

The scaffold ``model.py`` targets an LSTM+Attention operating directly on
the raw 96 h × 15 timestep tensor. That architecture needs TensorFlow +
real training data to be useful; while we wait on both, this module
reduces each window to a hand-engineered summary feature vector that a
tree-based classifier can learn from on the synthetic Tokadeh frame
produced by :mod:`ai.enviroguard.data.export`.

The feature extraction is deterministic, dependency-light (numpy only),
and ships with the baseline ONNX artifact — so operators who inspect
``artifacts/features_spec.json`` know exactly what every column means.

For a 96 h × 15-feature window we emit (per feature):

    mean, std, min, max, last_value, slope_per_hour

Plus a short global suffix pulled from the window's final row:

    hour_sin, hour_cos, wet_season_flag, rainfall_mm_24h, rainfall_mm_1h

Total: 15 × 6 + 5 = 95 features per window.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

#: Per-feature summary stats, in the fixed order every window emits.
PER_FEATURE_STATS: tuple[str, ...] = (
    "mean", "std", "min", "max", "last", "slope_per_hour",
)

#: Global features taken from the window's final row.
GLOBAL_FEATURES: tuple[str, ...] = (
    "hour_sin", "hour_cos", "wet_season_flag",
    "rainfall_mm_24h", "rainfall_mm_1h",
)


def feature_names(input_features: Iterable[str]) -> list[str]:
    """Return the output column names for a given sequence feature list.

    Order matches :func:`extract_window_features` so the ONNX artifact
    and the runtime stay in sync.
    """

    names: list[str] = []
    for f in input_features:
        for stat in PER_FEATURE_STATS:
            names.append(f"{f}__{stat}")
    names.extend(GLOBAL_FEATURES)
    return names


def _per_feature_stats(window: np.ndarray) -> np.ndarray:
    """Return (n_features, 6) summary stats for one 96 h × n_features window."""

    # window: (T, F). F is the number of raw sequence features.
    T, F = window.shape
    mean = window.mean(axis=0)
    std = window.std(axis=0)
    minv = window.min(axis=0)
    maxv = window.max(axis=0)
    last = window[-1, :]
    # Slope per hour: least-squares fit on the last 24 h (@15 min = 96 steps).
    # Falls back to the full window when it's shorter than 24 h.
    tail = window[-min(96, T) :, :]
    xs = np.arange(tail.shape[0], dtype=np.float32)
    # Center so numerical conditioning stays sane.
    xs = xs - xs.mean()
    denom = (xs * xs).sum() or 1.0
    slope_per_step = (tail - tail.mean(axis=0)).T @ xs / denom
    slope_per_hour = slope_per_step * 4.0  # 4 steps per hour at 15-min cadence
    stats = np.stack([mean, std, minv, maxv, last, slope_per_hour], axis=1)
    return stats.astype(np.float32)


def extract_window_features(
    window: np.ndarray,
    *,
    hour_sin: float,
    hour_cos: float,
    wet_season_flag: float,
    rainfall_mm_24h: float,
    rainfall_mm_1h: float,
) -> np.ndarray:
    """Reduce one 96 h × F window + global context to a flat feature vector.

    Returns a 1-D ``np.float32`` array of length ``F * 6 + 5``.
    """

    if window.ndim != 2:
        raise ValueError(f"window must be 2-D (T, F); got shape {window.shape}")
    stats = _per_feature_stats(window)  # (F, 6)
    tail = np.array(
        [hour_sin, hour_cos, wet_season_flag, rainfall_mm_24h, rainfall_mm_1h],
        dtype=np.float32,
    )
    return np.concatenate([stats.ravel(), tail]).astype(np.float32)


def expected_dim(n_sequence_features: int) -> int:
    """Length of the vector :func:`extract_window_features` produces."""

    return n_sequence_features * len(PER_FEATURE_STATS) + len(GLOBAL_FEATURES)
