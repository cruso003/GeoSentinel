"""Offline Ed25519 signing for compliance PDFs (Phase 3 §IFC PDF).

Covers the happy-path sign/verify roundtrip, tamper detection, dev-key
auto-generation + persistence across calls, and the pubkey mismatch
safeguard. The signing module writes to the user's home unless
``GEOSENTINEL_HOME`` is set — we pin it to ``tmp_path`` for test isolation.
"""

from __future__ import annotations

import pytest

pytest.importorskip("cryptography")

from app.services import report_signing as rs
from app.services.report_signing import (
    ReportSigningError,
    clear_cache,
    sign_pdf,
    verify_pdf,
)


@pytest.fixture(autouse=True)
def _isolate_key(tmp_path, monkeypatch):
    """Every test gets its own dev key + cache so keys don't leak across runs."""

    monkeypatch.setenv("GEOSENTINEL_HOME", str(tmp_path))
    # Force the cached settings instance to reload (report_signing reads
    # ``settings.report_signing_privkey_path`` through ``get_settings()``).
    from app.core.config import get_settings

    get_settings.cache_clear()
    clear_cache()
    yield
    clear_cache()
    get_settings.cache_clear()


def test_sign_and_verify_roundtrip():
    pdf = b"%PDF-1.4\nfake report body\n%%EOF"
    sig, pubkey = sign_pdf(pdf)
    assert len(sig) == 64
    assert len(pubkey) == 64  # 32-byte key hex-encoded
    assert verify_pdf(pdf, sig, pubkey) is True


def test_verify_detects_tampered_pdf():
    pdf = b"%PDF-1.4\nclean body\n%%EOF"
    sig, pubkey = sign_pdf(pdf)
    tampered = pdf.replace(b"clean", b"dirty")
    assert verify_pdf(tampered, sig, pubkey) is False


def test_verify_detects_wrong_pubkey():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives import serialization

    pdf = b"%PDF-1.4\nbody\n%%EOF"
    sig, _pubkey = sign_pdf(pdf)
    # Another freshly-generated pubkey shouldn't verify our signature.
    other_pub = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    assert verify_pdf(pdf, sig, other_pub) is False


def test_sign_rejects_empty_pdf():
    with pytest.raises(ReportSigningError, match="empty PDF"):
        sign_pdf(b"")


def test_verify_rejects_malformed_pubkey_hex():
    pdf = b"%PDF-1.4\nbody\n%%EOF"
    sig, _ = sign_pdf(pdf)
    with pytest.raises(ReportSigningError, match="not valid hex"):
        verify_pdf(pdf, sig, "not-hex")


def test_verify_rejects_wrong_pubkey_length():
    pdf = b"%PDF-1.4\nbody\n%%EOF"
    sig, _ = sign_pdf(pdf)
    with pytest.raises(ReportSigningError, match="32 bytes"):
        verify_pdf(pdf, sig, "aa" * 16)


def test_verify_rejects_wrong_signature_length():
    pdf = b"%PDF-1.4\nbody\n%%EOF"
    _, pubkey = sign_pdf(pdf)
    with pytest.raises(ReportSigningError, match="64 bytes"):
        verify_pdf(pdf, b"\x00" * 32, pubkey)


def test_dev_key_persists_across_calls(tmp_path):
    """First call creates the key file, second call reuses it — same pubkey."""

    pdf = b"%PDF-1.4\nbody\n%%EOF"
    _, pub1 = sign_pdf(pdf)
    clear_cache()  # force reload from disk
    _, pub2 = sign_pdf(pdf)
    assert pub1 == pub2
    key_path = tmp_path / "report_signing.pem"
    assert key_path.exists()


def test_configured_privkey_path_pubkey_mismatch_refused(tmp_path, monkeypatch):
    """If ``report_signing_pubkey`` is set but doesn't match the private
    key's derived pubkey we refuse to sign — catches silent key rotation."""

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    priv = Ed25519PrivateKey.generate()
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    keyfile = tmp_path / "real_key.pem"
    keyfile.write_bytes(pem)

    # Point settings at the real key but claim a *different* pubkey.
    bogus_pubkey = "bb" * 32
    monkeypatch.setattr(
        rs, "get_settings", lambda: _FakeSettings(
            report_signing_privkey_path=str(keyfile),
            report_signing_pubkey=bogus_pubkey,
        )
    )
    clear_cache()

    with pytest.raises(ReportSigningError, match="does not match"):
        sign_pdf(b"%PDF-1.4\nbody\n%%EOF")


def test_configured_privkey_path_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(
        rs, "get_settings", lambda: _FakeSettings(
            report_signing_privkey_path=str(tmp_path / "nope.pem"),
            report_signing_pubkey="",
        )
    )
    clear_cache()
    with pytest.raises(ReportSigningError, match="does not exist"):
        sign_pdf(b"%PDF-1.4\nbody\n%%EOF")


class _FakeSettings:
    def __init__(self, *, report_signing_privkey_path: str, report_signing_pubkey: str):
        self.report_signing_privkey_path = report_signing_privkey_path
        self.report_signing_pubkey = report_signing_pubkey
