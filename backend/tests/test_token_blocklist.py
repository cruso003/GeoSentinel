"""JTI blocklist fallback (Phase 2.1 §8)."""

import time

import pytest

from app.services import token_blocklist as tb


@pytest.fixture(autouse=True)
def _reset():
    tb.reset_for_tests()
    yield
    tb.reset_for_tests()


def test_in_process_revoke_and_check():
    blk = tb._InProcessBlocklist()
    blk.revoke("jti-1", ttl_s=60)
    assert blk.is_revoked("jti-1") is True
    assert blk.is_revoked("jti-other") is False


def test_in_process_sweeps_expired():
    blk = tb._InProcessBlocklist()
    blk._expiry["jti-expired"] = time.time() - 1
    blk._expiry["jti-fresh"] = time.time() + 60
    assert blk.is_revoked("jti-expired") is False
    assert blk.is_revoked("jti-fresh") is True


def test_in_process_zero_ttl_is_noop():
    blk = tb._InProcessBlocklist()
    blk.revoke("jti-zero", ttl_s=0)
    assert blk.is_revoked("jti-zero") is False


@pytest.mark.asyncio
async def test_revoke_and_is_revoked_use_fallback(monkeypatch):
    monkeypatch.setattr(tb, "aioredis", None)
    monkeypatch.setattr(tb, "_redis_client", None)
    monkeypatch.setattr(tb, "_redis_tried", True)

    await tb.revoke("jti-a", ttl_s=60)
    assert await tb.is_revoked("jti-a") is True
    assert await tb.is_revoked("jti-b") is False


def test_remaining_ttl_s_handles_missing_exp():
    assert tb.remaining_ttl_s({}) == 0


def test_remaining_ttl_s_clamps_negative():
    assert tb.remaining_ttl_s({"exp": time.time() - 100}) == 0
