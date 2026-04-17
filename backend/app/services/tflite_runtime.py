"""Thin TFLite inference wrapper used by enviroguard.py + slopewatch.py.

Tries `tflite_runtime` first (slim), falls back to `tensorflow.lite` if the
full TF install is present. Returns None if neither is available or the
artifact file is missing, which lets the inference services fall back to
their deterministic synthetic behaviour.

Phase 2.1 §5: scalers are loaded from `scaler.json` only. We refuse to read
`scaler.pkl` so a writable model directory cannot become an RCE vector.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import numpy as np

log = logging.getLogger(__name__)

_INTERPRETERS: dict[str, Any] = {}
_SCALERS: dict[str, "Scaler"] = {}
_METADATA: dict[str, dict] = {}
_lock = Lock()


@dataclass(frozen=True)
class Scaler:
    mean: np.ndarray
    scale: np.ndarray

    def apply(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.scale


def _try_interpreter(model_path: Path):  # pragma: no cover
    try:
        from tflite_runtime.interpreter import Interpreter  # type: ignore

        interp = Interpreter(model_path=str(model_path))
    except Exception:
        try:
            import tensorflow as tf  # type: ignore

            interp = tf.lite.Interpreter(model_path=str(model_path))
        except Exception as e:
            log.info("TFLite unavailable (%s); inference will fall back.", e)
            return None
    interp.allocate_tensors()
    return interp


def _artifact_dir(name: str) -> Path:
    root = Path(os.environ.get("GEOSENTINEL_MODEL_DIR", "/app/ai"))
    return root / name / "artifacts"


def _load_scaler(art: Path) -> Optional[Scaler]:
    # Phase 2.1 §5: pickle is an RCE surface. Refuse to touch it.
    legacy = art / "scaler.pkl"
    if legacy.exists():
        log.error(
            "Refusing to load legacy %s. Retrain with the current pipeline to emit scaler.json.",
            legacy,
        )
        return None
    path = art / "scaler.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    try:
        mean = np.asarray(raw["mean"], dtype=np.float32)
        scale = np.asarray(raw["scale"], dtype=np.float32)
    except KeyError as e:
        log.error("scaler.json at %s missing required key %s", path, e)
        return None
    if mean.shape != scale.shape:
        log.error("scaler.json at %s mean/scale shape mismatch", path)
        return None
    return Scaler(mean=mean, scale=scale)


def load(name: str) -> Optional[dict]:
    """Return {interpreter, scaler, metadata} or None."""
    with _lock:
        if name in _INTERPRETERS:
            return _bundle(name)
        art = _artifact_dir(name)
        model = art / f"{name}.tflite"
        if not model.exists():
            log.info("No TFLite artifact for %s at %s; using synthetic fallback.", name, model)
            return None
        interp = _try_interpreter(model)
        if interp is None:
            return None
        _INTERPRETERS[name] = interp
        scaler = _load_scaler(art)
        if scaler is not None:
            _SCALERS[name] = scaler
        meta = art / "metadata.json"
        if meta.exists():
            _METADATA[name] = json.loads(meta.read_text())
        return _bundle(name)


def _bundle(name: str) -> dict:
    return {
        "interpreter": _INTERPRETERS.get(name),
        "scaler": _SCALERS.get(name),
        "metadata": _METADATA.get(name, {}),
    }


def clear_cache() -> None:
    """Test helper: drop cached interpreters/scalers/metadata."""
    with _lock:
        _INTERPRETERS.clear()
        _SCALERS.clear()
        _METADATA.clear()


def invoke(name: str, x: np.ndarray) -> Optional[np.ndarray]:
    """Run inference. x shape = (batch, seq, features). Returns None on failure."""
    bundle = load(name)
    if not bundle:
        return None
    interp = bundle["interpreter"]
    scaler: Optional[Scaler] = bundle.get("scaler")
    if scaler is not None:
        x = scaler.apply(x)
    x = x.astype(np.float32, copy=False)
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    interp.resize_tensor_input(inp["index"], x.shape)
    interp.allocate_tensors()
    interp.set_tensor(inp["index"], x)
    interp.invoke()
    return interp.get_tensor(out["index"])
