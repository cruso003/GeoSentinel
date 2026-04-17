"""Per-gateway credential minting + parsing (Phase 2.1 §7)."""

import pytest

pytest.importorskip("passlib")

from app.services import gateway_auth


def test_mint_key_shape():
    plaintext, prefix, hashed = gateway_auth.mint_key()
    assert plaintext.startswith("gs_")
    parts = plaintext.split("_", 2)
    assert len(parts) == 3
    assert parts[1] == prefix
    assert len(parts[1]) == gateway_auth._PREFIX_LEN
    assert len(parts[2]) == gateway_auth._SECRET_LEN
    assert hashed and hashed != parts[2]


def test_mint_keys_are_unique():
    seen = set()
    for _ in range(25):
        plaintext, _, _ = gateway_auth.mint_key()
        assert plaintext not in seen
        seen.add(plaintext)


def test_split_accepts_well_formed_key():
    plaintext, prefix, _ = gateway_auth.mint_key()
    parsed = gateway_auth._split(plaintext)
    assert parsed is not None
    assert parsed[0] == prefix


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-key",
        "gs_short_secret",
        "gs_" + "a" * 12 + "_short",
        "gs_" + "a" * 13 + "_" + "b" * 32,
        "bearer abc",
    ],
)
def test_split_rejects_malformed(bad: str):
    assert gateway_auth._split(bad) is None


def test_allowed_nodes_returns_none_when_unrestricted():
    class FakeGW:
        allowed_node_ids = None

    assert gateway_auth.allowed_nodes(FakeGW()) is None


def test_allowed_nodes_returns_set():
    class FakeGW:
        allowed_node_ids = ["env-1", "env-2"]

    assert gateway_auth.allowed_nodes(FakeGW()) == {"env-1", "env-2"}
