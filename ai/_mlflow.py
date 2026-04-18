"""MLflow integration shim shared by ai/enviroguard and ai/slopewatch.

Keeps training scripts clean: if ``MLFLOW_TRACKING_URI`` is set we log
params/metrics/artifacts; if it isn't (or mlflow isn't installed), the
context manager becomes a no-op so ``python -m ai.enviroguard.train`` still
works on a laptop without staging infra up.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def data_checksum(path: Path, chunk: int = 1 << 20) -> str:
    """SHA-256 of the training file so an MLflow run is pinned to its
    exact inputs — without this, 'which data was this model trained on?'
    is unanswerable after a refresh."""

    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class _NullRun:
    """Drop-in shim when MLflow is unavailable. Every method is a no-op so
    the caller doesn't branch on ``if mlflow_available``."""

    def log_params(self, *_a: Any, **_kw: Any) -> None: ...
    def log_metrics(self, *_a: Any, **_kw: Any) -> None: ...
    def log_metric(self, *_a: Any, **_kw: Any) -> None: ...
    def log_artifact(self, *_a: Any, **_kw: Any) -> None: ...
    def log_dict(self, *_a: Any, **_kw: Any) -> None: ...
    def set_tags(self, *_a: Any, **_kw: Any) -> None: ...


class _MLflowRun:
    """Thin wrapper around the real ``mlflow`` SDK. Exposes only the
    surface the training scripts use so swapping trackers later is a
    single-file change."""

    def __init__(self, mlflow_mod):
        self._mlflow = mlflow_mod

    def log_params(self, params: dict[str, Any]) -> None:
        self._mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        self._mlflow.log_metrics(metrics, step=step)

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        self._mlflow.log_metric(key, value, step=step)

    def log_artifact(self, path: str | Path, artifact_path: str | None = None) -> None:
        self._mlflow.log_artifact(str(path), artifact_path=artifact_path)

    def log_dict(self, d: dict, name: str) -> None:
        self._mlflow.log_dict(d, name)

    def set_tags(self, tags: dict[str, str]) -> None:
        self._mlflow.set_tags(tags)


@contextlib.contextmanager
def start_run(experiment: str, run_name: str | None = None, tags: dict | None = None):
    """Yield a run handle. When MLflow is unreachable (no server, no pkg,
    no env var) we yield a silent stub instead of crashing — training
    should still complete locally."""

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    if not tracking_uri:
        log.info("MLFLOW_TRACKING_URI unset; skipping experiment tracking.")
        yield _NullRun()
        return

    try:
        import mlflow  # type: ignore
    except Exception as e:
        log.warning("mlflow import failed (%s); skipping experiment tracking.", e)
        yield _NullRun()
        return

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name):
        if tags:
            mlflow.set_tags(tags)
        yield _MLflowRun(mlflow)


def write_run_manifest(out_dir: Path, manifest: dict) -> Path:
    """Dump a ``run.json`` alongside the artifacts so an operator without
    MLflow access can still trace a deployed model back to its config."""

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "run.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return path
