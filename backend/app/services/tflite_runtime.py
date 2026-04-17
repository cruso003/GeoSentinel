"""Thin TFLite inference wrapper used by enviroguard.py + slopewatch.py.

Tries `tflite_runtime` first (slim), falls back to `tensorflow.lite` if the
full TF install is present. Returns None if neither is available or the
artifact file is missing, which lets the inference services fall back to
their deterministic synthetic behaviour.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import numpy as np

log = logging.getLogger(__name__)

_INTERPRETERS: dict[str, Any] = {}
_SCALERS: dict[str, Any] = {}
_METADATA: dict[str, dict] = {}
_lock = Lock()


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


def load(name: str) -> Optional[dict]:
    """Return {interpreter, scaler_mean, scaler_scale, metadata} or None."""
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
        scaler_pkl = art / "scaler.pkl"
        if scaler_pkl.exists():
            with scaler_pkl.open("rb") as fh:
                _SCALERS[name] = pickle.load(fh)
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


def invoke(name: str, x: np.ndarray) -> Optional[np.ndarray]:
    """Run inference. x shape = (batch, seq, features). Returns None on failure."""
    bundle = load(name)
    if not bundle:
        return None
    interp = bundle["interpreter"]
    scaler = bundle.get("scaler")
    if scaler is not None:
        x = (x - scaler.mean_) / scaler.scale_
    x = x.astype(np.float32, copy=False)
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    interp.resize_tensor_input(inp["index"], x.shape)
    interp.allocate_tensors()
    interp.set_tensor(inp["index"], x)
    interp.invoke()
    return interp.get_tensor(out["index"])
