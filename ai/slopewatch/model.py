"""SlopeWatch — Physics-Informed Neural Network (PINN) architecture (Spec §13.2).

The model consumes ≥72h of multivariate geotechnical data and emits a risk
score ∈ [0,1]. A custom loss term penalises the distance between the NN
prediction and the Mohr-Coulomb FoS-derived risk on simulated slip surfaces
(see physics/mohr_coulomb.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


SEQUENCE_LENGTH = 288  # 72h at 15-min resolution

FEATURES: List[str] = [
    "tilt_x",
    "tilt_y",
    "crack_displacement",
    "pore_pressure",
    "seismic_magnitude",
    "rainfall_mm_1h",
    "rainfall_mm_24h",
    "insar_displacement_mm",  # ESA Sentinel-1 InSAR time series
    "slope_height_m",
    "slope_angle_deg",
]


@dataclass
class ModelSpec:
    sequence_length: int = SEQUENCE_LENGTH
    n_features: int = len(FEATURES)
    gru_units: tuple[int, ...] = (96, 48)
    dense_tower: tuple[int, ...] = (64, 32, 16)
    physics_lambda: float = 0.25  # weight on Mohr-Coulomb loss term
    dropout: float = 0.2


def build_model():  # pragma: no cover - TF optional
    try:
        from tensorflow import keras
        from tensorflow.keras import layers
    except Exception as e:
        raise RuntimeError("TensorFlow not installed for SlopeWatch training.") from e

    s = ModelSpec()
    inputs = keras.Input(shape=(s.sequence_length, s.n_features))
    x = layers.GRU(s.gru_units[0], return_sequences=True)(inputs)
    x = layers.Dropout(s.dropout)(x)
    x = layers.GRU(s.gru_units[1])(x)
    for units in s.dense_tower:
        x = layers.Dense(units, activation="relu")(x)
        x = layers.Dropout(s.dropout)(x)
    risk = layers.Dense(1, activation="sigmoid", name="risk_score")(x)
    return keras.Model(inputs, risk, name="SlopeWatch_PINN")
