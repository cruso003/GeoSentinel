"""Thin TFLite inference wrapper used by enviroguard.py + slopewatch.py.

Tries `tflite_runtime` first (slim), falls back to `tensorflow.lite` if the
full TF install is present. Returns None if neither is available or the
artifact file is missing, which lets the inference services fall back to
their deterministic synthetic behaviour.

Phase 2.1 §5: scalers are loaded from `scaler.json` only. We refuse to read
`scaler.pkl` so a writable model directory cannot become an RCE vector.

Phase 2.4 §4: artifacts ship with an Ed25519 detached signature
(``<name>.tflite.sig``, 64 raw bytes). In production we refuse to load an
unsigned or mis-signed model — an attacker who can drop a file in the
model volume must also possess the offline private key to have their
weights honoured.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from ..core.config import get_settings

log = logging.getLogger(__name__)

_INTERPRETERS: dict[str, Any] = {}
_SCALERS: dict[str, Scaler] = {}
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


class ModelSignatureError(RuntimeError):
    """Raised when an artifact's signature is missing or invalid under a
    configuration that requires it (production, or an explicit opt-in)."""


def _verify_signature(model_path: Path) -> bool:
    """Verify ``<model>.sig`` against ``settings.model_signing_pubkey``.

    Returns True if the signature is present and valid. Returns False when
    signature enforcement is disabled *and* the signature is absent — the
    caller decides whether to hard-fail.
    """

    settings = get_settings()
    sig_path = model_path.with_suffix(model_path.suffix + ".sig")
    pubkey_hex = (settings.model_signing_pubkey or "").strip()
    required = settings.is_production or settings.model_signing_required

    if not pubkey_hex:
        if required:
            raise ModelSignatureError(
                f"model_signing_pubkey is unset but signature enforcement is on "
                f"({model_path.name})"
            )
        log.warning(
            "Loading %s without signature check (no pubkey configured).",
            model_path.name,
        )
        return False

    if not sig_path.exists():
        if required:
            raise ModelSignatureError(
                f"Signature {sig_path.name} missing; refusing to load model."
            )
        log.warning("No signature for %s; loading unverified.", model_path.name)
        return False

    try:
        # Local import so environments without cryptography can still use
        # synthetic fallback paths during dev.
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except Exception as e:  # pragma: no cover
        if required:
            raise ModelSignatureError(
                "cryptography is required for signature verification"
            ) from e
        log.warning("cryptography unavailable (%s); skipping signature check.", e)
        return False

    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
    except ValueError as e:
        raise ModelSignatureError("model_signing_pubkey is not valid hex") from e
    if len(pubkey_bytes) != 32:
        raise ModelSignatureError(
            "model_signing_pubkey must decode to 32 bytes (Ed25519)"
        )

    sig = sig_path.read_bytes()
    if len(sig) != 64:
        raise ModelSignatureError(
            f"Signature file {sig_path.name} is not 64 bytes"
        )
    try:
        Ed25519PublicKey.from_public_bytes(pubkey_bytes).verify(
            sig, model_path.read_bytes()
        )
    except InvalidSignature as e:
        raise ModelSignatureError(
            f"Signature verification failed for {model_path.name}"
        ) from e
    log.info("Signature verified for %s.", model_path.name)
    return True


def _load_scaler(art: Path) -> Scaler | None:
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


def load(name: str) -> dict | None:
    """Return {interpreter, scaler, metadata} or None."""
    with _lock:
        if name in _INTERPRETERS:
            return _bundle(name)
        art = _artifact_dir(name)
        model = art / f"{name}.tflite"
        if not model.exists():
            log.info("No TFLite artifact for %s at %s; using synthetic fallback.", name, model)
            return None
        # Verify first — an invalid signature in production raises; in dev
        # we log and continue so local work doesn't need a signing ceremony.
        _verify_signature(model)
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


def invoke(name: str, x: np.ndarray) -> np.ndarray | None:
    """Run inference. x shape = (batch, seq, features). Returns None on failure."""
    bundle = load(name)
    if not bundle:
        return None
    interp = bundle["interpreter"]
    scaler: Scaler | None = bundle.get("scaler")
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
