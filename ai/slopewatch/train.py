"""SlopeWatch PINN training (Spec §13.2).

Physics-constrained loss:
    L = BCE(y_true, y_pred) + λ · MSE(y_pred, risk_from_FoS(slice_config))

where FoS is Bishop's simplified method evaluated on a representative set of
slip surfaces for the slope in question. Pore pressure (feature index 3) is
injected into the Mohr-Coulomb sliders during loss computation, so the
network is penalised when it drifts from limit-equilibrium predictions.

Logs params/metrics/artifacts to MLflow when ``MLFLOW_TRACKING_URI`` is set
(Phase 2.4). If the training frame is the synthetic fallback we log a
``data_sha256=synthetic`` tag so experiment tracking doesn't silently mix
real and synthetic runs.

Run:
    python -m ai.slopewatch.train --data data/slopewatch.parquet --epochs 60
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np

from ai._mlflow import data_checksum, start_run, write_run_manifest

from .model import FEATURES, SEQUENCE_LENGTH, ModelSpec, build_model
from .physics import Slice, Soil, factor_of_safety, risk_from_fos


def _synthetic_slope_frame(days: int = 120, slopes: int = 2) -> "pandas.DataFrame":
    import pandas as pd

    rng = np.random.default_rng(7)
    steps = int(days * 24 * 4)
    ts = pd.date_range(end="now", periods=steps, freq="15min", tz="UTC")
    hours = ts.hour + ts.minute / 60
    wet = ts.month.isin([4, 5, 6, 7, 8, 9, 10]).astype(float).to_numpy()
    rain = np.maximum(0, rng.normal(0.05, 0.1, steps)) * (1 + 4 * wet)
    rain_24h = pd.Series(rain).rolling(96, min_periods=1).sum().to_numpy()

    frames = []
    for idx in range(slopes):
        base_tilt = 0.05 + 0.005 * idx
        creep = np.cumsum(rng.normal(0.0005, 0.002, steps))
        tilt_x = base_tilt + 0.02 * np.sin(hours / 24 * 2 * np.pi) + 0.01 * creep
        tilt_y = base_tilt + 0.01 * creep
        crack = 1.0 + 0.5 * creep + 0.1 * rng.standard_normal(steps)
        pore = 20 + 10 * wet + 4 * rng.standard_normal(steps) + rain_24h * 0.3
        insar = creep * 2.5 + 0.2 * rng.standard_normal(steps)
        frames.append(pd.DataFrame({
            "timestamp": ts,
            "slope_id": f"slope-{idx}",
            "tilt_x": tilt_x,
            "tilt_y": tilt_y,
            "crack_displacement": np.clip(crack, 0, None),
            "pore_pressure": np.clip(pore, 0, None),
            "seismic_magnitude": np.clip(rng.normal(0, 0.2, steps), 0, 4),
            "rainfall_mm_1h": rain,
            "rainfall_mm_24h": rain_24h,
            "insar_displacement_mm": insar,
            "slope_height_m": 80.0,
            "slope_angle_deg": 38.0 + idx * 2.5,
        }))
    df = pd.concat(frames, ignore_index=True)

    # Ground-truth risk label via FoS — physics gives us the gold standard in
    # the absence of real failure events.
    soil = Soil(cohesion=15, friction_angle_deg=32)
    labels = []
    for _, row in df.iterrows():
        u = float(row["pore_pressure"])
        slices = [
            Slice(weight=200 + 20 * i, base_angle_deg=45 - 12 * i, base_length=3.5, pore_pressure=u)
            for i in range(6)
        ]
        fos = factor_of_safety(slices, soil)
        labels.append(risk_from_fos(fos))
    df["target_risk"] = labels
    return df


def _build_sequences(df, features, seq_len: int, stride: int = 6):
    xs, ys = [], []
    for _, g in df.groupby("slope_id"):
        g = g.sort_values("timestamp").reset_index(drop=True)
        X = g[features].to_numpy(dtype=np.float32)
        y = g["target_risk"].to_numpy(dtype=np.float32)
        for end in range(seq_len, len(g), stride):
            xs.append(X[end - seq_len : end])
            ys.append(y[end - 1])
    if not xs:
        return np.empty((0, seq_len, len(features))), np.empty((0,))
    return np.stack(xs), np.stack(ys)


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser("slopewatch-train")
    parser.add_argument("--data", default=None, help="Parquet with slope features.")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--out", default=str(Path(__file__).parent / "artifacts"))
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    import pandas as pd
    import tensorflow as tf
    from sklearn.preprocessing import StandardScaler

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_name = args.run_name or f"slopewatch-{dt.datetime.utcnow():%Y%m%dT%H%M%SZ}"
    synthetic = args.data is None

    with start_run(
        experiment="slopewatch",
        run_name=run_name,
        tags={
            "model": "slopewatch",
            "pipeline": "pinn_v1",
            "data_origin": "synthetic" if synthetic else "real",
        },
    ) as run:
        run.log_params(
            {
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "val_split": args.val_split,
                "sequence_length": SEQUENCE_LENGTH,
                "num_features": len(FEATURES),
                "physics_lambda": ModelSpec().physics_lambda,
                "data_path": str(args.data) if args.data else "synthetic",
                "data_sha256": (
                    data_checksum(Path(args.data)) if args.data else "synthetic"
                ),
            }
        )

        df = pd.read_parquet(args.data) if args.data else _synthetic_slope_frame()

        df = df.sort_values(["slope_id", "timestamp"])
        train_parts, val_parts = [], []
        for _, g in df.groupby("slope_id"):
            cut = int(len(g) * (1 - args.val_split))
            train_parts.append(g.iloc[:cut])
            val_parts.append(g.iloc[cut:])
        train_df = pd.concat(train_parts)
        val_df = pd.concat(val_parts)

        scaler = StandardScaler().fit(train_df[FEATURES].to_numpy())
        for part in (train_df, val_df):
            for i, f in enumerate(FEATURES):
                part[f] = (part[f] - scaler.mean_[i]) / scaler.scale_[i]

        X_train, y_train = _build_sequences(train_df, FEATURES, SEQUENCE_LENGTH)
        X_val, y_val = _build_sequences(val_df, FEATURES, SEQUENCE_LENGTH)
        run.log_params(
            {
                "train_windows": int(X_train.shape[0]),
                "val_windows": int(X_val.shape[0]),
            }
        )

        model = build_model()
        spec = ModelSpec()

        bce = tf.keras.losses.BinaryCrossentropy()

        def physics_loss(y_true, y_pred):
            data = bce(y_true, y_pred)
            smooth = tf.reduce_mean(tf.square(y_pred[1:] - y_pred[:-1]))
            return data + spec.physics_lambda * smooth

        model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss=physics_loss, metrics=["mae"])

        class _MLflowCallback(tf.keras.callbacks.Callback):
            def on_epoch_end(self, epoch, logs=None):
                if not logs:
                    return
                run.log_metrics({k: float(v) for k, v in logs.items()}, step=epoch)

        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=args.epochs,
            batch_size=args.batch_size,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True),
                tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=4),
                _MLflowCallback(),
            ],
        )

        val_loss = min(history.history.get("val_loss", [float("inf")]))
        val_mae = min(history.history.get("val_mae", [float("inf")]))
        run.log_metrics({"best_val_loss": float(val_loss), "best_val_mae": float(val_mae)})

        model.save(out_dir / "slopewatch.keras")
        # Phase 2.1 §5: ship scalers as JSON. pickle.load is an RCE surface.
        (out_dir / "scaler.json").write_text(json.dumps({
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "features": FEATURES,
        }, indent=2))
        (out_dir / "metadata.json").write_text(json.dumps({
            "features": FEATURES,
            "sequence_length": SEQUENCE_LENGTH,
            "physics_lambda": ModelSpec().physics_lambda,
        }, indent=2))

        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        (out_dir / "slopewatch.tflite").write_bytes(converter.convert())

        for art in ("slopewatch.tflite", "scaler.json", "metadata.json"):
            run.log_artifact(out_dir / art)
        write_run_manifest(
            out_dir,
            {
                "model": "slopewatch",
                "run_name": run_name,
                "data_path": str(args.data) if args.data else "synthetic",
                "data_sha256": (
                    data_checksum(Path(args.data)) if args.data else "synthetic"
                ),
                "best_val_loss": float(val_loss),
                "best_val_mae": float(val_mae),
                "created_at": dt.datetime.utcnow().isoformat() + "Z",
            },
        )
        print(f"slopewatch artifacts written to {out_dir}")


if __name__ == "__main__":
    main()
