"""Loader safety for tflite_runtime (Phase 2.1 §5).

We don't exercise actual TFLite inference here — the wrapper is designed to
be best-effort and return None when the runtime or artifacts are missing.
What we *do* lock down is the scaler loader: JSON accepted, pickle refused.
"""

import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
tr = pytest.importorskip("app.services.tflite_runtime")


@pytest.fixture(autouse=True)
def _clear_cache():
    tr.clear_cache()
    yield
    tr.clear_cache()


def _write_scaler_json(art: Path, mean, scale) -> None:
    art.mkdir(parents=True, exist_ok=True)
    (art / "scaler.json").write_text(
        json.dumps({"mean": list(mean), "scale": list(scale), "features": []})
    )


def test_load_scaler_reads_json(tmp_path: Path):
    art = tmp_path / "enviroguard" / "artifacts"
    _write_scaler_json(art, [1.0, 2.0, 3.0], [0.5, 1.0, 2.0])
    scaler = tr._load_scaler(art)
    assert scaler is not None
    np.testing.assert_allclose(scaler.mean, [1.0, 2.0, 3.0])
    np.testing.assert_allclose(scaler.scale, [0.5, 1.0, 2.0])


def test_load_scaler_apply_normalises(tmp_path: Path):
    art = tmp_path / "m" / "artifacts"
    _write_scaler_json(art, [1.0, 2.0], [0.5, 2.0])
    scaler = tr._load_scaler(art)
    x = np.array([[1.0, 2.0], [2.0, 6.0]], dtype=np.float32)
    out = scaler.apply(x)
    np.testing.assert_allclose(out, [[0.0, 0.0], [2.0, 2.0]])


def test_load_scaler_refuses_pickle(tmp_path: Path, caplog):
    art = tmp_path / "m" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    # Even an empty file with that name must be refused — we never unpickle.
    (art / "scaler.pkl").write_bytes(b"cos\nsystem\n(S'id'\ntR.")
    with caplog.at_level("ERROR"):
        scaler = tr._load_scaler(art)
    assert scaler is None
    assert any("scaler.pkl" in rec.message for rec in caplog.records)


def test_load_scaler_missing_returns_none(tmp_path: Path):
    art = tmp_path / "nope" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    assert tr._load_scaler(art) is None


def test_load_scaler_rejects_shape_mismatch(tmp_path: Path, caplog):
    art = tmp_path / "m" / "artifacts"
    _write_scaler_json(art, [1.0, 2.0, 3.0], [0.5, 1.0])
    with caplog.at_level("ERROR"):
        assert tr._load_scaler(art) is None


def test_load_missing_model_returns_none(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GEOSENTINEL_MODEL_DIR", str(tmp_path))
    assert tr.load("enviroguard") is None
