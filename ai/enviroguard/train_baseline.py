"""Train the EnviroGuard baseline — 7 GradientBoostingClassifiers, one per
exceedance head, exported to ONNX so :mod:`backend.app.services.onnx_runtime`
can serve them without needing TensorFlow at inference time.

This baseline exists so the production inference path is no longer
``sin(hour_of_day)``. Each head is a real trained classifier scored on a
held-out time window; metrics land next to the artifacts in
``run_manifest.json`` so a reviewer sees exactly how it was evaluated.

Current training data: the deterministic synthetic Tokadeh frame built
by :func:`ai.enviroguard.data.export._synthetic_frame`, which models the
site's wet-season rainfall, diurnal pH/DO drift, and PM2.5 patterns.
Pre-incubation swaps this for real OpenAQ Monrovia air quality data,
operator-provided water-quality logs, and (eventually) ArcelorMittal
Nimba telemetry — the training script accepts a ``--parquet`` input, so
switching is one argument change.

Run (synthetic baseline shipped in-tree)::

    python -m ai.enviroguard.train_baseline

Run (bring your own labelled parquet)::

    python -m ai.enviroguard.train_baseline --parquet data/real.parquet \\
        --out ai/enviroguard/artifacts
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .data.export import _label, _synthetic_frame
from .features import (
    GLOBAL_FEATURES,
    PER_FEATURE_STATS,
    expected_dim,
    extract_window_features,
    feature_names,
)
from .model import FEATURES, OUTPUT_HEADS, SEQUENCE_LENGTH

log = logging.getLogger(__name__)

# Window stride during feature extraction: emit one feature vector every
# this many 15-min steps. 4 → 1 window per hour → ~900 windows per node
# per 15-day frame; keeps training sub-minute while still covering the
# ``rainfall_event`` + ``tailings_seepage`` scenarios the mock engine
# knows about.
_WINDOW_STRIDE = 4

# Columns in the raw frame that aren't part of the sequence tensor itself
# but we want to carry per-window for the GLOBAL_FEATURES tail.
_WINDOW_END_COLUMNS = (
    "hour_of_day_sin",
    "hour_of_day_cos",
    "wet_season_flag",
    "rainfall_mm_24h",
    "rainfall_mm_1h",
)

# Target columns _label() emits (reaching into export.py keeps the label
# definitions in one place).
_TARGET_COLUMNS = (
    "target_ph_24h",
    "target_turbidity_24h",
    "target_dissolved_oxygen_24h",
    "target_conductivity_24h",
    "target_pm25_24h",
    "target_ph_72h",
    "target_turbidity_72h",
)


def _load_frame(parquet_path: str | None, days: int) -> "object":
    """Return a labelled training frame; synthetic when no parquet given."""

    import pandas as pd  # local import to keep module import cheap

    if parquet_path:
        log.info("loading %s", parquet_path)
        df = pd.read_parquet(parquet_path)
    else:
        log.info("generating synthetic Tokadeh frame (%d days)", days)
        df = _synthetic_frame(days=days, node_ids=["ENV-01", "ENV-02", "ENV-03"])
    df = _label(df)
    # Drop head windows that got NaN labels from the forward-shift —
    # _label fills them with 0 but the trailing windows have no future to
    # verify, so leaving them in biases precision.
    before = len(df)
    df = df.dropna(subset=list(_TARGET_COLUMNS))
    log.info("rows: %d (dropped %d trailing-no-label rows)", len(df), before - len(df))
    return df


def _build_windows(df: "object") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(X_features, Y_targets, timestamps)`` for every window
    whose end row has valid labels. ``X_features`` is 2-D (N, D)."""

    import pandas as pd

    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    ts: list[pd.Timestamp] = []
    for _, group in df.groupby("node_id"):
        g = group.sort_values("timestamp").reset_index(drop=True)
        seq = g[list(FEATURES)].to_numpy(dtype=np.float32)
        targets = g[list(_TARGET_COLUMNS)].to_numpy(dtype=np.float32)
        tail_vals = g[list(_WINDOW_END_COLUMNS)].to_numpy(dtype=np.float32)
        for end in range(SEQUENCE_LENGTH, len(g), _WINDOW_STRIDE):
            window = seq[end - SEQUENCE_LENGTH : end]
            tail = tail_vals[end - 1]
            feats = extract_window_features(
                window,
                hour_sin=float(tail[0]),
                hour_cos=float(tail[1]),
                wet_season_flag=float(tail[2]),
                rainfall_mm_24h=float(tail[3]),
                rainfall_mm_1h=float(tail[4]),
            )
            xs.append(feats)
            ys.append(targets[end - 1])
            ts.append(g["timestamp"].iloc[end - 1])
    if not xs:
        raise SystemExit("No training windows produced — check the input frame.")
    return np.stack(xs), np.stack(ys), np.array(ts)


def _time_split(timestamps: np.ndarray, val_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """Return boolean (train_mask, val_mask) split on time, globally. We
    pick a single cutoff so training never sees future windows — any
    performance number here is honest about leakage."""

    order = np.argsort(timestamps)
    cutoff = int(len(order) * (1 - val_frac))
    train_idx = order[:cutoff]
    val_idx = order[cutoff:]
    train_mask = np.zeros(len(timestamps), dtype=bool)
    val_mask = np.zeros(len(timestamps), dtype=bool)
    train_mask[train_idx] = True
    val_mask[val_idx] = True
    return train_mask, val_mask


def _fit_and_export_head(
    X_train, y_train, X_val, y_val, head: str, out_dir: Path, seed: int
) -> dict:
    """Train one GradientBoostingClassifier for ``head``, export to ONNX,
    return holdout metrics."""

    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        roc_auc_score,
    )
    from skl2onnx import to_onnx
    from skl2onnx.common.data_types import FloatTensorType

    pos_rate_train = float(y_train.mean())
    if pos_rate_train in (0.0, 1.0):
        # Degenerate head: synthetic frame didn't produce two classes in
        # this horizon.  Fit a tiny LogisticRegression on a 2-example
        # stub so the exported ONNX graph has a valid probability output
        # (always ~constant); runtime handles the low-info case the same
        # as any other prediction.
        from sklearn.linear_model import LogisticRegression

        log.warning(
            "head %s has pos_rate=%.3f — fitting a degenerate stub model",
            head, pos_rate_train,
        )
        stub_X = np.vstack([X_train[:1], X_train[:1]])
        stub_y = np.array([0, 1])
        clf = LogisticRegression(max_iter=50)
        clf.fit(stub_X, stub_y)
    else:
        clf = GradientBoostingClassifier(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            random_state=seed,
        )
        clf.fit(X_train, y_train)

    # ONNX export. Explicit input shape + zipmap=False so the output is a
    # plain probability tensor the runtime can consume as (N, 2).
    initial_type = [("X", FloatTensorType([None, X_train.shape[1]]))]
    onnx_model = to_onnx(
        clf,
        initial_types=initial_type,
        target_opset=18,
        options={id(clf): {"zipmap": False}},
    )
    (out_dir / f"enviroguard__{head}.onnx").write_bytes(onnx_model.SerializeToString())

    probs = clf.predict_proba(X_val)[:, 1]
    pos_rate_val = float(y_val.mean())
    metrics = {
        "head": head,
        "n_train": int(X_train.shape[0]),
        "n_val": int(X_val.shape[0]),
        "pos_rate_train": pos_rate_train,
        "pos_rate_val": pos_rate_val,
    }
    # Scoring is only meaningful when both classes exist in the holdout.
    if 0 < pos_rate_val < 1:
        metrics["roc_auc"] = float(roc_auc_score(y_val, probs))
        metrics["pr_auc"] = float(average_precision_score(y_val, probs))
        metrics["brier"] = float(brier_score_loss(y_val, probs))
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
        metrics["brier"] = None
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser("enviroguard-train-baseline")
    parser.add_argument("--parquet", default=None, help="Labelled training frame; synthetic if omitted.")
    parser.add_argument("--days", type=int, default=20, help="Days of synthetic data to generate.")
    parser.add_argument("--val-frac", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "artifacts"),
        help="Where to write the ONNX files + run_manifest.json.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _load_frame(args.parquet, args.days)
    X, Y, ts = _build_windows(df)
    log.info("built %d windows, feature dim=%d", X.shape[0], X.shape[1])
    assert X.shape[1] == expected_dim(len(FEATURES)), (
        f"feature dim mismatch: got {X.shape[1]}, expected {expected_dim(len(FEATURES))}"
    )

    train_mask, val_mask = _time_split(ts, args.val_frac)
    log.info("time split: train=%d val=%d", train_mask.sum(), val_mask.sum())

    # Per-head metrics.
    metrics: list[dict] = []
    heads = tuple(
        head.replace("target_", "") for head in _TARGET_COLUMNS
    )  # ph_24h, turbidity_24h, …
    for i, (head, output_name) in enumerate(zip(heads, OUTPUT_HEADS)):
        row_metrics = _fit_and_export_head(
            X[train_mask], Y[train_mask, i],
            X[val_mask], Y[val_mask, i],
            head=head,
            out_dir=out_dir,
            seed=args.seed,
        )
        row_metrics["output_head"] = output_name
        log.info(
            "head %s: pr_auc=%s roc_auc=%s pos_val=%.3f",
            head,
            f"{row_metrics['pr_auc']:.3f}" if row_metrics["pr_auc"] is not None else "n/a",
            f"{row_metrics['roc_auc']:.3f}" if row_metrics["roc_auc"] is not None else "n/a",
            row_metrics["pos_rate_val"],
        )
        metrics.append(row_metrics)

    # Explicit mapping output_head -> ONNX file name so the backend
    # runtime doesn't have to guess the filename convention.
    head_files = {
        output: f"enviroguard__{short}.onnx"
        for short, output in zip(heads, OUTPUT_HEADS)
    }
    # Metadata consumed by the runtime at inference time.
    metadata = {
        "model_family": "enviroguard_baseline_gbm_v1",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sequence_length": SEQUENCE_LENGTH,
        "sequence_features": list(FEATURES),
        "per_feature_stats": list(PER_FEATURE_STATS),
        "global_features": list(GLOBAL_FEATURES),
        "feature_names": feature_names(FEATURES),
        "feature_dim": expected_dim(len(FEATURES)),
        "output_heads": list(OUTPUT_HEADS),
        "head_files": head_files,
        "data_source": "synthetic" if args.parquet is None else os.path.basename(args.parquet),
        "days": args.days if args.parquet is None else None,
        "window_stride": _WINDOW_STRIDE,
        "val_frac": args.val_frac,
        "seed": args.seed,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (out_dir / "run_manifest.json").write_text(
        json.dumps({"metadata": metadata, "metrics_per_head": metrics}, indent=2)
    )

    print(f"wrote {len(heads)} ONNX heads + metadata.json + run_manifest.json to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
