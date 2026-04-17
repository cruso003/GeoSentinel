"""EnviroGuard training (Spec §13.1).

Pipeline:
  1. Load Parquet from `ai.enviroguard.data.export`.
  2. Sequence-ise: 96 h look-back windows at 15-min resolution = 384 timesteps.
  3. Per-feature StandardScaler fit on train split only.
  4. Train LSTM+Attention with binary-crossentropy over 7 outputs.
  5. Early-stopping + ReduceLROnPlateau on val AUC.
  6. Export: full Keras model + scaler + a TFLite artifact for on-node inference.

Run:
    python -m ai.enviroguard.train --data data/enviroguard.parquet --epochs 40
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

import numpy as np

from .model import FEATURES, OUTPUT_HEADS, SEQUENCE_LENGTH, build_model


def _build_sequences(
    df,
    features: list[str],
    targets: list[str],
    seq_len: int,
    stride: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Slice time-ordered rows per node into overlapping 96 h windows."""
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for _, group in df.groupby("node_id"):
        g = group.sort_values("timestamp").reset_index(drop=True)
        X = g[features].to_numpy(dtype=np.float32)
        Y = g[targets].to_numpy(dtype=np.float32)
        for end in range(seq_len, len(g), stride):
            xs.append(X[end - seq_len : end])
            ys.append(Y[end - 1])
    if not xs:
        return np.empty((0, seq_len, len(features))), np.empty((0, len(targets)))
    return np.stack(xs), np.stack(ys)


def main() -> None:  # pragma: no cover - training entrypoint
    parser = argparse.ArgumentParser("enviroguard-train")
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "artifacts"),
    )
    args = parser.parse_args()

    import pandas as pd
    from sklearn.preprocessing import StandardScaler
    import tensorflow as tf

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.data)
    targets = [f"target_{h}" for h in (
        "ph_24h", "turbidity_24h", "dissolved_oxygen_24h",
        "conductivity_24h", "pm25_24h", "ph_72h", "turbidity_72h",
    )]
    for t in targets:
        if t not in df.columns:
            raise SystemExit(f"Training frame missing target: {t}")

    # Hold out the last fraction of time per node for validation.
    df = df.sort_values(["node_id", "timestamp"])
    train_parts, val_parts = [], []
    for _, g in df.groupby("node_id"):
        cut = int(len(g) * (1 - args.val_split))
        train_parts.append(g.iloc[:cut])
        val_parts.append(g.iloc[cut:])
    train_df = pd.concat(train_parts)
    val_df = pd.concat(val_parts)

    scaler = StandardScaler().fit(train_df[FEATURES].to_numpy())
    train_df = train_df.assign(**{
        f: (train_df[f] - scaler.mean_[i]) / scaler.scale_[i]
        for i, f in enumerate(FEATURES)
    })
    val_df = val_df.assign(**{
        f: (val_df[f] - scaler.mean_[i]) / scaler.scale_[i]
        for i, f in enumerate(FEATURES)
    })

    X_train, y_train = _build_sequences(train_df, FEATURES, targets, SEQUENCE_LENGTH)
    X_val, y_val = _build_sequences(val_df, FEATURES, targets, SEQUENCE_LENGTH)
    print(f"train: {X_train.shape}  val: {X_val.shape}")

    model = build_model()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=[tf.keras.metrics.AUC(name="auc"), "binary_accuracy"],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_auc", mode="max", patience=6, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_auc", mode="max", factor=0.5, patience=3),
    ]
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
    )

    model.save(out_dir / "enviroguard.keras")
    with open(out_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(out_dir / "metadata.json", "w") as f:
        json.dump({
            "features": FEATURES,
            "output_heads": OUTPUT_HEADS,
            "sequence_length": SEQUENCE_LENGTH,
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
        }, f, indent=2)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_bytes = converter.convert()
    (out_dir / "enviroguard.tflite").write_bytes(tflite_bytes)
    print(f"artifacts written to {out_dir}")


if __name__ == "__main__":
    main()
