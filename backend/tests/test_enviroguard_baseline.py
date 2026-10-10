"""End-to-end test for the EnviroGuard ONNX baseline.

The brutal review flagged that every production inference path returned
``sin(hour_of_day)`` or hard-coded constants. The baseline wired in
``services/enviroguard.py`` replaces the ``sin`` surrogate with a real
trained model served over ``onnxruntime``.

These tests prove the pipeline runs:

- ``onnx_runtime.load`` discovers the baked-in artifact directory and
  loads every head listed in ``metadata.json``.
- ``invoke_head`` produces a probability in [0, 1] for every head when
  fed a realistic feature vector.
- ``run_enviroguard`` returns a prediction with the baseline confidence
  (0.65), not the surrogate confidence (0.5), when no telemetry has
  flowed yet — proving the service picked the baseline over the sine
  surrogate.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from app.services import onnx_runtime  # noqa: E402

_ARTIFACTS = Path(__file__).resolve().parents[2] / "ai" / "enviroguard" / "artifacts"


@pytest.fixture(autouse=True)
def _reset_runtime_cache():
    """Drop the module-level session dict between tests so an artifact
    swap in one test does not bleed into the next."""

    onnx_runtime.clear_cache()
    yield
    onnx_runtime.clear_cache()


@pytest.mark.skipif(
    not (_ARTIFACTS / "metadata.json").exists(),
    reason="EnviroGuard baseline artifacts not built; run train_baseline.py.",
)
def test_runtime_loads_every_head():
    assert onnx_runtime.load() is True
    md = onnx_runtime.metadata()
    assert md is not None
    assert md["model_family"] == "enviroguard_baseline_gbm_v1"
    expected_heads = md["output_heads"]
    loaded = set(onnx_runtime.available_heads())
    # Every head declared in metadata must have a loaded session.
    missing = [h for h in expected_heads if h not in loaded]
    assert not missing, f"missing ONNX heads: {missing}"


@pytest.mark.skipif(
    not (_ARTIFACTS / "metadata.json").exists(),
    reason="EnviroGuard baseline artifacts not built; run train_baseline.py.",
)
def test_invoke_head_returns_probabilities():
    import numpy as np

    assert onnx_runtime.load() is True
    md = onnx_runtime.metadata()
    assert md is not None
    feat = np.zeros(md["feature_dim"], dtype=np.float32)
    for head in md["output_heads"]:
        p = onnx_runtime.invoke_head(head, feat)
        assert p is not None, f"head {head} returned None"
        assert 0.0 <= p <= 1.0, f"head {head} out of range: {p}"


@pytest.mark.skipif(
    not (_ARTIFACTS / "metadata.json").exists(),
    reason="EnviroGuard baseline artifacts not built; run train_baseline.py.",
)
def test_metadata_has_head_file_mapping():
    """The runtime loads per-head ONNX files by explicit name, so the
    training script must write the mapping into metadata.json. Catches
    an earlier bug where the service couldn't find ``do_exceedance_24h``
    because the file was called ``dissolved_oxygen_24h.onnx``."""

    md = json.loads((_ARTIFACTS / "metadata.json").read_text())
    assert "head_files" in md, "head_files mapping missing from metadata.json"
    for head in md["output_heads"]:
        assert head in md["head_files"], f"no file mapping for {head}"
        assert (_ARTIFACTS / md["head_files"][head]).exists(), (
            f"metadata points at {md['head_files'][head]} but file is absent"
        )


@pytest.mark.skipif(
    not (_ARTIFACTS / "metadata.json").exists(),
    reason="EnviroGuard baseline artifacts not built; run train_baseline.py.",
)
def test_run_enviroguard_uses_baseline_when_tflite_absent(monkeypatch):
    """``run_enviroguard`` should serve the baseline's prediction when
    no TFLite artifact is loaded — proving the service picked the
    middle rung of the inference ladder rather than the ``sin(hour)``
    surrogate at the bottom."""

    from app.services import enviroguard

    # Force the TFLite path to no-op so we're guaranteed to fall through.
    async def _no_sequence(_site):
        return None

    monkeypatch.setattr(enviroguard, "_assemble_sequence", _no_sequence)

    pred = asyncio.run(enviroguard.run_enviroguard("tokadeh-liberia"))
    # The baseline reports confidence 0.65; the hour-of-day surrogate
    # reports 0.5. Any value in [0.6, 0.7] identifies the baseline path.
    assert 0.6 <= pred.confidence <= 0.7, (
        f"confidence={pred.confidence} suggests surrogate path, not baseline"
    )
    # Probabilities must be well-formed floats in [0, 1].
    for attr in (
        "ph_exceedance_24h",
        "turbidity_exceedance_24h",
        "do_exceedance_24h",
        "conductivity_exceedance_24h",
        "pm25_exceedance_24h",
        "ph_exceedance_72h",
        "turbidity_exceedance_72h",
    ):
        v = getattr(pred, attr)
        assert isinstance(v, float), f"{attr}={v!r} is not a float"
        assert 0.0 <= v <= 1.0, f"{attr}={v} out of [0, 1]"
