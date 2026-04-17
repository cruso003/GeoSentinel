"""EnviroGuard — LSTM+Attention multi-output exceedance predictor (Spec §13.1).

Phase 2 will train on ≥18 months of InfluxDB exports and deploy via TFLite.
This module holds only the architecture + feature spec so the shape is pinned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# 96h history @ 15-min resolution = 384 timesteps.
SEQUENCE_LENGTH = 384

# Multivariate features across all env nodes aggregated (see ingestion pipeline).
FEATURES: List[str] = [
    "ph", "turbidity", "dissolved_oxygen", "conductivity", "temperature",
    "pm25", "pm10", "so2", "no2", "noise_db",
    "rainfall_mm_1h", "rainfall_mm_24h",
    "wet_season_flag", "hour_of_day_sin", "hour_of_day_cos",
]

# 7 outputs: 5 parameters × 24h exceedance prob, plus 2 × 72h (pH, turbidity).
OUTPUT_HEADS: List[str] = [
    "ph_exceedance_24h",
    "turbidity_exceedance_24h",
    "do_exceedance_24h",
    "conductivity_exceedance_24h",
    "pm25_exceedance_24h",
    "ph_exceedance_72h",
    "turbidity_exceedance_72h",
]


@dataclass
class ModelSpec:
    sequence_length: int = SEQUENCE_LENGTH
    n_features: int = len(FEATURES)
    n_outputs: int = len(OUTPUT_HEADS)
    lstm_units_stack: tuple[int, ...] = (128, 64)
    attention_heads: int = 4
    attention_key_dim: int = 32
    dropout: float = 0.2
    dense_tower: tuple[int, ...] = (64, 32)


def build_model():  # pragma: no cover - requires TF at runtime
    """Build the Keras model. Stubbed here; implemented in Phase 2."""
    try:
        from tensorflow import keras
        from tensorflow.keras import layers
    except Exception as e:
        raise RuntimeError("TensorFlow not installed for EnviroGuard training.") from e

    spec = ModelSpec()
    inputs = keras.Input(shape=(spec.sequence_length, spec.n_features))
    x = layers.LSTM(spec.lstm_units_stack[0], return_sequences=True)(inputs)
    x = layers.Dropout(spec.dropout)(x)
    x = layers.LSTM(spec.lstm_units_stack[1], return_sequences=True)(x)
    attn = layers.MultiHeadAttention(
        num_heads=spec.attention_heads, key_dim=spec.attention_key_dim
    )(x, x)
    x = layers.GlobalAveragePooling1D()(attn)
    for units in spec.dense_tower:
        x = layers.Dense(units, activation="relu")(x)
        x = layers.Dropout(spec.dropout)(x)
    outputs = layers.Dense(spec.n_outputs, activation="sigmoid", name="exceedance_probs")(x)
    return keras.Model(inputs, outputs, name="EnviroGuard_LSTM_Attn")
