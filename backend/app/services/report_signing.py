"""Ed25519 offline signing for compliance PDFs (Phase 3 §IFC PDF).

Mirrors the TFLite artifact signing in ``tflite_runtime._verify_signature``:
the private key stays out of the database, in a filesystem path
configured via ``settings.report_signing_privkey_path``. At report
generation time the backend builds a canonical signing envelope that
binds the report's identity (report_id, site_id, report_type, period
start/end) to the SHA-256 of the PDF bytes, signs that envelope, and
stores the detached signature + public key fingerprint alongside the
report.

The envelope matters: an earlier revision signed the PDF bytes alone,
which meant two reports' metadata could be swapped in-DB and both
signatures still verified against each other's PDFs. The envelope
anchors every signature to the specific report it was issued for.

In dev, if no private key is configured we auto-generate an ephemeral
key at ``~/.geosentinel/report_signing.pem`` and log a warning. The
pubkey hex is derived from it so a developer can still verify. In
production the settings validator refuses to boot without both
``report_signing_privkey_path`` and ``report_signing_pubkey`` explicitly
configured — see ``core/config.py``.

External verifiers don't need to trust the backend; they receive:

    - the PDF bytes (via the download endpoint)
    - the signing envelope + detached signature (via the public
      ``GET /reports/{id}/signature`` endpoint)
    - the pubkey hex (same endpoint)

and can verify independently with any Ed25519 library — recompute the
envelope JSON from the response fields + the PDF's SHA-256, then
Ed25519-verify.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

from ..core.config import get_settings

log = logging.getLogger(__name__)

_key_lock = Lock()
_cached_privkey: Any | None = None
_cached_pubkey_hex: str | None = None


class ReportSigningError(RuntimeError):
    """Raised when signing or verification cannot be performed safely."""


def _dev_key_path() -> Path:
    home = Path(os.environ.get("GEOSENTINEL_HOME", str(Path.home() / ".geosentinel")))
    home.mkdir(parents=True, exist_ok=True)
    return home / "report_signing.pem"


def _load_or_generate_dev_key() -> tuple[Any, str]:
    """Return (private key, pubkey hex) for dev/local runs.

    The key persists in ``~/.geosentinel/report_signing.pem`` so successive
    runs produce the same pubkey — important so a reviewer can re-verify a
    signature they captured earlier.
    """

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    path = _dev_key_path()
    if path.exists():
        try:
            priv = serialization.load_pem_private_key(path.read_bytes(), password=None)
            if not isinstance(priv, Ed25519PrivateKey):
                raise ReportSigningError(
                    f"Key at {path} is not an Ed25519 private key"
                )
        except Exception as e:
            raise ReportSigningError(f"Could not load dev signing key {path}: {e}") from e
    else:
        log.warning(
            "No report_signing_privkey_path configured; generating ephemeral "
            "dev key at %s. Configure an offline key before shipping.",
            path,
        )
        priv = Ed25519PrivateKey.generate()
        pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        try:
            # Best-effort tighten perms; not fatal on filesystems that don't
            # honour POSIX modes (e.g. some CI containers).
            path.chmod(0o600)
        except OSError:
            pass
    pub = priv.public_key()
    pub_hex = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return priv, pub_hex


def _load_private_key() -> tuple[Any, str]:
    """Return (Ed25519 private key, pubkey hex), caching across calls.

    The cache is a simple process-local singleton guarded by ``_key_lock``
    — report signing is not on the hot path and this keeps lifecycle
    concerns out of the API layer.
    """

    global _cached_privkey, _cached_pubkey_hex
    with _key_lock:
        if _cached_privkey is not None and _cached_pubkey_hex is not None:
            return _cached_privkey, _cached_pubkey_hex

        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except Exception as e:  # pragma: no cover - dependency always present
            raise ReportSigningError(
                "cryptography is required for report signing"
            ) from e

        settings = get_settings()
        path_setting = (settings.report_signing_privkey_path or "").strip()
        if path_setting:
            key_path = Path(path_setting)
            if not key_path.exists():
                raise ReportSigningError(
                    f"report_signing_privkey_path={key_path} does not exist"
                )
            priv = serialization.load_pem_private_key(
                key_path.read_bytes(), password=None
            )
            if not isinstance(priv, Ed25519PrivateKey):
                raise ReportSigningError(
                    f"{key_path} is not an Ed25519 PEM private key"
                )
            pub_hex_raw = priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()
            configured = (settings.report_signing_pubkey or "").strip().lower()
            if configured and configured != pub_hex_raw:
                raise ReportSigningError(
                    "report_signing_pubkey does not match the public key derived "
                    "from report_signing_privkey_path; refusing to sign"
                )
            priv, pub_hex = priv, pub_hex_raw
        else:
            priv, pub_hex = _load_or_generate_dev_key()

        _cached_privkey = priv
        _cached_pubkey_hex = pub_hex
        return priv, pub_hex


def clear_cache() -> None:
    """Test helper — drop the cached private key so settings changes take
    effect within a single process."""

    global _cached_privkey, _cached_pubkey_hex
    with _key_lock:
        _cached_privkey = None
        _cached_pubkey_hex = None


#: Envelope schema version. Bump when the field set or canonicalisation
#: changes so verifiers can tell whether they understand the signature.
ENVELOPE_VERSION = 1


def build_envelope(
    *,
    report_id: str,
    site_id: str,
    report_type: str,
    period_start: str,
    period_end: str,
    pdf_bytes: bytes,
) -> dict:
    """Return the canonical signing envelope for a compliance report.

    The envelope binds the report's identity to the exact PDF bytes that
    were issued — swapping metadata or substituting a different PDF
    breaks verification.  ``period_start`` and ``period_end`` are ISO
    strings so the envelope is stable across language stacks.
    """

    return {
        "v": ENVELOPE_VERSION,
        "report_id": report_id,
        "site_id": site_id,
        "report_type": report_type,
        "period_start": period_start,
        "period_end": period_end,
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
    }


def canonicalize_envelope(envelope: dict) -> bytes:
    """Deterministic JSON encoding of the envelope — sorted keys, no
    extra whitespace, UTF-8. Verifiers reproduce exactly this to feed
    into Ed25519.verify."""

    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_report(envelope: dict, pdf_bytes: bytes) -> tuple[bytes, str]:
    """Sign a canonicalised report envelope + the PDF's SHA-256.

    Returns ``(signature, pubkey_hex)``. The envelope must have been built
    with ``build_envelope`` — in particular its ``pdf_sha256`` field is
    cross-checked against ``pdf_bytes`` so a caller can't accidentally
    sign a stale hash.
    """

    if not pdf_bytes:
        raise ReportSigningError("refusing to sign empty PDF")
    expected_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if envelope.get("pdf_sha256") != expected_hash:
        raise ReportSigningError(
            "envelope pdf_sha256 does not match the supplied PDF bytes"
        )
    priv, pub_hex = _load_private_key()
    sig = priv.sign(canonicalize_envelope(envelope))
    return sig, pub_hex


def verify_report(
    envelope: dict, pdf_bytes: bytes, signature: bytes, pubkey_hex: str
) -> bool:
    """Verify a detached signature over an envelope + PDF.

    Returns True on success, False on any signature / key / hash mismatch.
    Raises ``ReportSigningError`` only for malformed input that would make
    the check meaningless (wrong key length, non-hex pubkey, bad envelope).
    """

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except Exception as e:  # pragma: no cover
        raise ReportSigningError(
            "cryptography is required for report signature verification"
        ) from e

    try:
        pub_bytes = bytes.fromhex(pubkey_hex)
    except ValueError as e:
        raise ReportSigningError("pubkey_hex is not valid hex") from e
    if len(pub_bytes) != 32:
        raise ReportSigningError("Ed25519 pubkey must decode to 32 bytes")
    if len(signature) != 64:
        raise ReportSigningError("Ed25519 signature must be 64 bytes")
    # Envelope must bind to the PDF the verifier actually has.
    actual_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if envelope.get("pdf_sha256") != actual_hash:
        return False
    if envelope.get("v") != ENVELOPE_VERSION:
        raise ReportSigningError(
            f"unknown envelope version {envelope.get('v')!r}; verifier only "
            f"understands v={ENVELOPE_VERSION}"
        )
    try:
        Ed25519PublicKey.from_public_bytes(pub_bytes).verify(
            signature, canonicalize_envelope(envelope)
        )
        return True
    except InvalidSignature:
        return False


def sign_pdf(pdf_bytes: bytes) -> tuple[bytes, str]:
    """Low-level bytes-only signing primitive — kept for callers that
    only need to sign a blob (e.g. the TFLite artifact signer path).

    Compliance reports should use ``sign_report`` so the signature binds
    to the full envelope and metadata cannot be swapped post-signing.
    """

    if not pdf_bytes:
        raise ReportSigningError("refusing to sign empty PDF")
    priv, pub_hex = _load_private_key()
    sig = priv.sign(pdf_bytes)
    return sig, pub_hex


def verify_pdf(pdf_bytes: bytes, signature: bytes, pubkey_hex: str) -> bool:
    """Low-level verification counterpart to ``sign_pdf``. See
    ``verify_report`` for the envelope-aware form compliance reports
    actually use."""

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except Exception as e:  # pragma: no cover
        raise ReportSigningError(
            "cryptography is required for report signature verification"
        ) from e

    try:
        pub_bytes = bytes.fromhex(pubkey_hex)
    except ValueError as e:
        raise ReportSigningError("pubkey_hex is not valid hex") from e
    if len(pub_bytes) != 32:
        raise ReportSigningError("Ed25519 pubkey must decode to 32 bytes")
    if len(signature) != 64:
        raise ReportSigningError("Ed25519 signature must be 64 bytes")
    try:
        Ed25519PublicKey.from_public_bytes(pub_bytes).verify(signature, pdf_bytes)
        return True
    except InvalidSignature:
        return False
