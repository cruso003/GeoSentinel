"""Backend-side loader + invoker for the EnviroGuard ONNX baseline.

The baseline model is a set of per-head ``GradientBoostingClassifier``
exports produced by ``ai/enviroguard/train_baseline.py``. Each ONNX file
takes a (1, D) float tensor and returns ``(label, probabilities)`` where
``probabilities[0, 1]`` is the probability of exceedance for that head.

Compared to :mod:`tflite_runtime` this module:

- loads ONNX via ``onnxruntime`` instead of TFLite — zero native TF
  dependency, works in a slim backend image;
- loads one artifact per output head (seven files) and runs them in
  sequence, so we can swap any individual head for a better model
  without a wholesale retrain;
- enforces the Ed25519 signature policy only when
  ``settings.model_signing_required`` is true (same contract as
  tflite_runtime — the production image refuses unsigned artifacts).

The feature extractor lives in ``ai.enviroguard.features``; this module
only invokes the frozen graphs. See the module docstring in
``ai/enviroguard/train_baseline.py`` for data provenance and metrics.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

import numpy as np

from ..core.config import get_settings

log = logging.getLogger(__name__)

# {head_name: {"session": InferenceSession, "input_name": str, "prob_name": str}}
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_METADATA: Optional[Dict[str, Any]] = None
_lock = Lock()


def _artifact_dir() -> Path:
    """Return the directory baseline ONNX heads live in.

    Honoured in priority order: GEOSENTINEL_MODEL_DIR env, the in-tree
    ai/enviroguard/artifacts path (Docker image bakes the whole repo in,
    so this resolves at runtime for the default deploy).
    """

    env_dir = os.environ.get("GEOSENTINEL_MODEL_DIR")
    if env_dir:
        return Path(env_dir) / "enviroguard" / "artifacts"
    # Repo-relative fallback — walks up from this file to the repo root.
    here = Path(__file__).resolve()
    repo = here.parents[3]  # backend/app/services/.. -> backend/app/.. -> backend/.. -> repo
    return repo / "ai" / "enviroguard" / "artifacts"


def _try_import_ort() -> Any | None:
    try:
        import onnxruntime as ort  # type: ignore

        return ort
    except Exception as e:
        log.info("onnxruntime unavailable (%s); baseline inference will be skipped.", e)
        return None


def _load_metadata(art_dir: Path) -> Dict[str, Any] | None:
    meta_path = art_dir / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception as e:
        log.warning("Could not read %s: %s", meta_path, e)
        return None


def _verify_optional_signature(art_dir: Path, head_file: Path) -> bool:
    """Baseline ONNX signing follows the same pattern as the TFLite path.

    If a ``<file>.sig`` exists we verify it; if production requires
    signing (``settings.model_signing_required``) we refuse to load an
    unsigned artifact. Dev / test deploys load unsigned artifacts and
    log a note. The pubkey comes from ``settings.model_signing_pubkey``.
    """

    settings = get_settings()
    sig_path = head_file.with_suffix(head_file.suffix + ".sig")
    if not sig_path.exists():
        if settings.model_signing_required:
            log.error("Refusing to load unsigned baseline artifact %s", head_file.name)
            return False
        return True
    pub_hex = (settings.model_signing_pubkey or "").strip()
    if not pub_hex:
        if settings.model_signing_required:
            log.error(
                "model_signing_required but model_signing_pubkey is unset — "
                "cannot verify %s",
                head_file.name,
            )
            return False
        return True
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        from cryptography.exceptions import InvalidSignature
    except Exception as e:  # pragma: no cover
        log.warning("cryptography missing (%s); cannot verify %s", e, head_file.name)
        return not settings.model_signing_required
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        pub.verify(sig_path.read_bytes(), head_file.read_bytes())
        return True
    except (InvalidSignature, ValueError) as e:
        log.error("Signature verification failed for %s: %s", head_file.name, e)
        return False


def load() -> bool:
    """Load all baseline heads once; subsequent calls short-circuit.

    Returns True when at least one head loaded successfully. The runtime
    tolerates individual missing heads — ``invoke_head()`` returns None
    for any output we don't have a session for, and the caller treats
    that as "model not available for this head".
    """

    global _METADATA

    with _lock:
        if _SESSIONS:
            return True
        ort = _try_import_ort()
        if ort is None:
            return False
        art_dir = _artifact_dir()
        if not art_dir.exists():
            log.info("baseline artifact dir %s not present; skipping", art_dir)
            return False
        meta = _load_metadata(art_dir)
        if meta is None:
            log.info("baseline metadata.json missing in %s; skipping", art_dir)
            return False
        _METADATA = meta
        file_map: Dict[str, str] = meta.get("head_files", {}) or {}
        for head in meta.get("output_heads", []):
            filename = file_map.get(head) or f"enviroguard__{head.replace('_exceedance_', '_')}.onnx"
            head_file = art_dir / filename
            if not head_file.exists():
                log.warning("baseline head %s: no ONNX file at %s", head, head_file)
                continue
            if not _verify_optional_signature(art_dir, head_file):
                continue
            try:
                sess = ort.InferenceSession(
                    str(head_file), providers=["CPUExecutionProvider"]
                )
                input_name = sess.get_inputs()[0].name
                output_names = [o.name for o in sess.get_outputs()]
                prob_name = _pick_prob_output(output_names)
                _SESSIONS[head] = {
                    "session": sess,
                    "input_name": input_name,
                    "prob_name": prob_name,
                    "sha256": hashlib.sha256(head_file.read_bytes()).hexdigest(),
                    "path": str(head_file),
                }
            except Exception as e:
                log.warning("failed to load baseline head %s: %s", head, e)
        if _SESSIONS:
            log.info(
                "enviroguard baseline: loaded %d/%d heads from %s",
                len(_SESSIONS),
                len(meta.get("output_heads", [])),
                art_dir,
            )
        else:
            log.info("enviroguard baseline: no heads loaded")
        return bool(_SESSIONS)


def _pick_prob_output(names: list[str]) -> str:
    """ONNX session returns (label, probabilities) for a classifier; some
    exports name them "label"/"probabilities", others "output_label"/
    "output_probability". Pick the one that looks like probabilities."""

    for n in names:
        if "prob" in n.lower():
            return n
    # Fallback: second output.
    return names[1] if len(names) > 1 else names[0]


def available_heads() -> list[str]:
    """Return the heads for which an ONNX session is loaded. Empty before
    :func:`load` has been called successfully."""

    return list(_SESSIONS.keys())


def metadata() -> Dict[str, Any] | None:
    return _METADATA


def invoke_head(head: str, features: np.ndarray) -> float | None:
    """Run the ONNX graph for ``head`` on a single (D,) feature vector.

    Returns the exceedance probability (float in [0, 1]) or None when the
    head is not loaded.
    """

    bundle = _SESSIONS.get(head)
    if bundle is None:
        return None
    x = np.asarray(features, dtype=np.float32).reshape(1, -1)
    try:
        outs = bundle["session"].run([bundle["prob_name"]], {bundle["input_name"]: x})
    except Exception as e:
        log.warning("baseline invoke_head(%s) failed: %s", head, e)
        return None
    probs = np.asarray(outs[0])
    # Shape (1, 2): col 1 is p(positive). Some exports flatten to (1,) when
    # there's only one class — degrade gracefully.
    if probs.ndim == 2 and probs.shape[1] >= 2:
        return float(probs[0, 1])
    return float(np.ravel(probs)[0])


def clear_cache() -> None:
    """Test helper — drop the loaded sessions so an artifact swap takes
    effect without a process restart."""

    global _METADATA
    with _lock:
        _SESSIONS.clear()
        _METADATA = None
