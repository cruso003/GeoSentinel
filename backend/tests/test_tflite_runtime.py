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


# --- Phase 2.4 §4: Ed25519 signature enforcement ----------------------


def _make_keypair():
    crypto = pytest.importorskip(
        "cryptography.hazmat.primitives.asymmetric.ed25519"
    )
    priv = crypto.Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub_bytes.hex()


def _reset_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_verify_signature_accepts_valid_signature(tmp_path: Path, monkeypatch):
    priv, pub_hex = _make_keypair()
    model = tmp_path / "enviroguard.tflite"
    model.write_bytes(b"fake-tflite-weights")
    (model.parent / "enviroguard.tflite.sig").write_bytes(
        priv.sign(model.read_bytes())
    )
    monkeypatch.setenv("MODEL_SIGNING_PUBKEY", pub_hex)
    monkeypatch.setenv("MODEL_SIGNING_REQUIRED", "true")
    _reset_settings_cache()
    try:
        assert tr._verify_signature(model) is True
    finally:
        _reset_settings_cache()


def test_verify_signature_rejects_tampered_model(tmp_path: Path, monkeypatch):
    priv, pub_hex = _make_keypair()
    model = tmp_path / "enviroguard.tflite"
    model.write_bytes(b"original")
    (model.parent / "enviroguard.tflite.sig").write_bytes(
        priv.sign(b"original")
    )
    # Tamper after signing.
    model.write_bytes(b"poisoned-weights")
    monkeypatch.setenv("MODEL_SIGNING_PUBKEY", pub_hex)
    monkeypatch.setenv("MODEL_SIGNING_REQUIRED", "true")
    _reset_settings_cache()
    try:
        with pytest.raises(tr.ModelSignatureError):
            tr._verify_signature(model)
    finally:
        _reset_settings_cache()


def test_verify_signature_requires_signature_when_enforced(
    tmp_path: Path, monkeypatch
):
    _, pub_hex = _make_keypair()
    model = tmp_path / "enviroguard.tflite"
    model.write_bytes(b"weights")
    monkeypatch.setenv("MODEL_SIGNING_PUBKEY", pub_hex)
    monkeypatch.setenv("MODEL_SIGNING_REQUIRED", "true")
    _reset_settings_cache()
    try:
        with pytest.raises(tr.ModelSignatureError):
            tr._verify_signature(model)
    finally:
        _reset_settings_cache()


def test_verify_signature_dev_mode_permits_unsigned(
    tmp_path: Path, monkeypatch, caplog
):
    # No pubkey, no enforcement → returns False and logs a warning.
    model = tmp_path / "enviroguard.tflite"
    model.write_bytes(b"weights")
    monkeypatch.delenv("MODEL_SIGNING_PUBKEY", raising=False)
    monkeypatch.delenv("MODEL_SIGNING_REQUIRED", raising=False)
    monkeypatch.setenv("ENV", "development")
    _reset_settings_cache()
    try:
        with caplog.at_level("WARNING"):
            assert tr._verify_signature(model) is False
    finally:
        _reset_settings_cache()


def test_verify_signature_rejects_malformed_pubkey(
    tmp_path: Path, monkeypatch
):
    model = tmp_path / "m.tflite"
    model.write_bytes(b"weights")
    (model.parent / "m.tflite.sig").write_bytes(b"\x00" * 64)
    monkeypatch.setenv("MODEL_SIGNING_PUBKEY", "nothex!!")
    monkeypatch.setenv("MODEL_SIGNING_REQUIRED", "true")
    _reset_settings_cache()
    try:
        with pytest.raises(tr.ModelSignatureError):
            tr._verify_signature(model)
    finally:
        _reset_settings_cache()
