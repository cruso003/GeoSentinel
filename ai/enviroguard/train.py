"""EnviroGuard training loop scaffold (Spec §13.1).

Phase 2 runbook:

  1. `python -m ai.enviroguard.data.export --site tokadeh-liberia --out data/tokadeh.parquet`
  2. `python -m ai.enviroguard.train --data data/tokadeh.parquet --epochs 40`
  3. TFLite conversion is written to ai/enviroguard/artifacts/enviroguard.tflite
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:  # pragma: no cover - stub
    parser = argparse.ArgumentParser("enviroguard-train")
    parser.add_argument("--data", required=True, help="Parquet of stacked env readings.")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "artifacts"),
        help="Directory for model + scaler + TFLite.",
    )
    args = parser.parse_args()

    try:
        import numpy as np  # noqa: F401
        import pandas as pd  # noqa: F401
        from sklearn.preprocessing import StandardScaler  # noqa: F401
        import tensorflow as tf  # noqa: F401
    except Exception as e:
        raise RuntimeError(
            "Training dependencies not installed. Install tensorflow, pandas, sklearn."
        ) from e

    os.makedirs(args.out, exist_ok=True)
    print(
        "EnviroGuard training is a Phase-2 deliverable. Data ingestion + "
        "scaler fit + .fit() loop + TFLite export go here."
    )


if __name__ == "__main__":
    main()
