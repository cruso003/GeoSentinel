"""Export the last N days of env telemetry from InfluxDB as a Parquet file.

Usage:
    python -m ai.enviroguard.data.export \\
        --site tokadeh-liberia --days 120 --out data/tokadeh.parquet

The output schema matches `ai.enviroguard.model.FEATURES` + one `target` column
per `OUTPUT_HEADS` head so `train.py` can read it directly. If InfluxDB is
unavailable, the script falls back to generating a synthetic dataset using
the frontend mock engine's math rewritten here in pure NumPy, so the training
pipeline can still exercise end-to-end in a clean checkout.
"""

from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ..model import FEATURES, OUTPUT_HEADS


IFC = {
    "ph": (6.0, 9.0),
    "turbidity": (None, 5.0),
    "dissolved_oxygen": (5.0, None),
    "conductivity": (None, 500.0),
    "pm25": (None, 25.0),
}


def _synthetic_frame(days: int, node_ids: Iterable[str]) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    steps = int(days * 24 * 4)  # 15-minute resolution
    ts = pd.date_range(
        end=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0),
        periods=steps,
        freq="15min",
    )
    hours = ts.hour + ts.minute / 60
    # Wet season: Apr–Oct in Liberia.
    wet = ts.month.isin([4, 5, 6, 7, 8, 9, 10]).astype(float).to_numpy()
    rain_background = np.maximum(0, rng.normal(0.05, 0.1, steps)) * (1 + 4 * wet)
    storm_mask = rng.random(steps) < 0.01
    storms = rain_background + storm_mask * rng.uniform(2, 15, steps)
    rain_24h = pd.Series(storms).rolling(window=96, min_periods=1).sum().to_numpy()

    frames = []
    for node in node_ids:
        ph = 7.6 + 0.2 * np.sin(hours / 24 * 2 * np.pi) + 0.05 * rng.standard_normal(steps)
        turb = 2.0 + 3.0 * wet + 0.8 * rng.standard_normal(steps) + storms * 0.4
        do = 8.0 - 0.5 * np.sin(hours / 24 * 2 * np.pi) + 0.2 * rng.standard_normal(steps)
        cond = 220 + 40 * wet + 15 * rng.standard_normal(steps)
        temp = 24 + 3 * np.sin((hours - 14) / 24 * 2 * np.pi) + 0.3 * rng.standard_normal(steps)
        pm25 = 15 + 8 * np.sin((hours - 18) / 24 * 2 * np.pi) + 2 * rng.standard_normal(steps)
        pm10 = pm25 * 1.6 + rng.uniform(2, 6, steps)
        so2 = np.clip(12 + 3 * rng.standard_normal(steps), 0, None)
        no2 = np.clip(18 + 4 * rng.standard_normal(steps), 0, None)
        noise = np.clip(55 + 10 * (wet * 0.3) + 3 * rng.standard_normal(steps), 30, None)
        frame = pd.DataFrame({
            "timestamp": ts,
            "node_id": node,
            "ph": ph,
            "turbidity": np.clip(turb, 0, None),
            "dissolved_oxygen": np.clip(do, 0, None),
            "conductivity": np.clip(cond, 0, None),
            "temperature": temp,
            "pm25": np.clip(pm25, 0, None),
            "pm10": np.clip(pm10, 0, None),
            "so2": so2,
            "no2": no2,
            "noise_db": noise,
            "rainfall_mm_1h": storms,
            "rainfall_mm_24h": rain_24h,
            "wet_season_flag": wet,
            "hour_of_day_sin": np.sin(hours / 24 * 2 * np.pi),
            "hour_of_day_cos": np.cos(hours / 24 * 2 * np.pi),
        })
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _label(df: pd.DataFrame) -> pd.DataFrame:
    """Derive binary exceedance labels 24 h / 72 h into the future per node."""
    df = df.sort_values(["node_id", "timestamp"]).reset_index(drop=True)
    out = df.copy()

    def _within(series: pd.Series, lo: float | None, hi: float | None) -> pd.Series:
        cond = pd.Series(False, index=series.index)
        if lo is not None:
            cond = cond | (series < lo)
        if hi is not None:
            cond = cond | (series > hi)
        return cond

    # 24 h = 96 steps; 72 h = 288 steps (at 15-min resolution).
    for param, (lo, hi) in IFC.items():
        breach = _within(df[param], lo, hi).astype(int)
        out[f"target_{param}_24h"] = (
            breach.groupby(df["node_id"]).transform(
                lambda x: x.rolling(96, min_periods=1).max().shift(-96).fillna(0)
            ).astype(int)
        )
        if param in ("ph", "turbidity"):
            out[f"target_{param}_72h"] = (
                breach.groupby(df["node_id"]).transform(
                    lambda x: x.rolling(288, min_periods=1).max().shift(-288).fillna(0)
                ).astype(int)
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser("enviroguard-export")
    parser.add_argument("--site", default="tokadeh-liberia")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--out", default="data/enviroguard.parquet")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Skip InfluxDB and generate synthetic training data.",
    )
    args = parser.parse_args()

    node_ids = ["ENV-01", "ENV-02", "ENV-03"]

    if args.synthetic or os.environ.get("GEOSENTINEL_FORCE_SYNTHETIC") == "1":
        df = _synthetic_frame(args.days, node_ids)
    else:
        try:
            df = _from_influx(args.site, args.days, node_ids)
        except Exception as e:
            print(f"InfluxDB unavailable ({e}); falling back to synthetic.")
            df = _synthetic_frame(args.days, node_ids)

    df = _label(df)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(
        f"Wrote {len(df):,} rows × {len(df.columns)} cols to {args.out} "
        f"({len(node_ids)} nodes, {args.days} days)."
    )


def _from_influx(site_id: str, days: int, node_ids: list[str]) -> pd.DataFrame:  # pragma: no cover
    """Query InfluxDB for the training window. Called only when reachable."""
    from influxdb_client import InfluxDBClient

    url = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    token = os.environ.get("INFLUXDB_TOKEN", "devtoken")
    org = os.environ.get("INFLUXDB_ORG", "geosentinel")
    bucket = os.environ.get("INFLUXDB_BUCKET", "sensor_data")
    stop = datetime.now(timezone.utc)
    start = stop - timedelta(days=days)
    node_filter = " or ".join(f'r["node_id"] == "{n}"' for n in node_ids)
    flux = f"""
    from(bucket:"{bucket}")
      |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
      |> filter(fn: (r) => r["_measurement"] == "env" and r["site_id"] == "{site_id}")
      |> filter(fn: (r) => {node_filter})
      |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
      |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
    """
    with InfluxDBClient(url=url, token=token, org=org) as client:
        df = client.query_api().query_data_frame(flux)
    if isinstance(df, list):
        df = pd.concat(df, ignore_index=True)
    df = df.rename(columns={"_time": "timestamp"})
    return df


if __name__ == "__main__":
    main()
