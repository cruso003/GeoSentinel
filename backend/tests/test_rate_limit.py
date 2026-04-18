"""Sliding-window rate limiter fallback (Phase 2.1 §4)."""

import asyncio

import pytest

from app.services.rate_limit import (
    RateLimitExceeded,
    _InProcessLimiter,
    hit,
    reset_for_tests,
)


def test_in_process_limiter_allows_up_to_limit():
    lim = _InProcessLimiter()
    for _ in range(5):
        lim.hit("k", limit=5, window_s=60)


def test_in_process_limiter_blocks_past_limit():
    lim = _InProcessLimiter()
    for _ in range(5):
        lim.hit("k", limit=5, window_s=60)
    with pytest.raises(RateLimitExceeded) as ei:
        lim.hit("k", limit=5, window_s=60)
    assert ei.value.retry_after_s > 0


def test_in_process_limiter_scopes_per_key():
    lim = _InProcessLimiter()
    for _ in range(5):
        lim.hit("alice", limit=5, window_s=60)
    # Different key gets its own bucket.
    lim.hit("bob", limit=5, window_s=60)


@pytest.mark.asyncio
async def test_hit_falls_back_when_redis_absent(monkeypatch):
    reset_for_tests()
    import app.services.rate_limit as rl

    monkeypatch.setattr(rl, "_redis", None)
    monkeypatch.setattr(rl, "aioredis", None)

    for _ in range(3):
        await hit("user:x", limit=3, window_s=60)
    with pytest.raises(RateLimitExceeded):
        await hit("user:x", limit=3, window_s=60)
