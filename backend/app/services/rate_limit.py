"""Sliding-window rate limiter backed by Redis.

Defence-in-depth for `/auth/login`. The edge nginx already caps 5 req/min per
IP; this layer caps per-email so an attacker rotating IPs can't grind through
users. Falls back to an in-process window when Redis is unreachable (no-op
in tests).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

try:  # Optional: Redis may be absent in tests.
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore

from ..core.config import get_settings

log = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a caller has exhausted its bucket. The HTTP layer maps this to 429."""

    def __init__(self, retry_after_s: int):
        super().__init__(f"Rate limit exceeded — retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


class _InProcessLimiter:
    """Fallback sliding-window limiter; good enough for dev + tests."""

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_s: int) -> None:
        now = time.monotonic()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window_s:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = int(window_s - (now - bucket[0])) + 1
            raise RateLimitExceeded(retry)
        bucket.append(now)


class _RedisLimiter:
    def __init__(self, url: str) -> None:
        assert aioredis is not None
        self._client = aioredis.from_url(url, encoding="utf-8", decode_responses=True)

    async def hit_async(self, key: str, *, limit: int, window_s: int) -> None:
        now_ms = int(time.time() * 1000)
        window_ms = window_s * 1000
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(key, 0, now_ms - window_ms)
        pipe.zadd(key, {f"{now_ms}-{id(object())}": now_ms})
        pipe.zcard(key)
        pipe.pexpire(key, window_ms)
        _, _, count, _ = await pipe.execute()
        if count > limit:
            raise RateLimitExceeded(window_s)


_fallback = _InProcessLimiter()
_redis: Optional[_RedisLimiter] = None


def _get_redis() -> Optional[_RedisLimiter]:
    global _redis
    if _redis is not None:
        return _redis
    if aioredis is None:
        return None
    try:
        _redis = _RedisLimiter(get_settings().redis_url)
    except Exception as e:  # pragma: no cover
        log.warning("rate_limit: redis unavailable (%s); using in-process fallback", e)
        _redis = None
    return _redis


async def hit(key: str, *, limit: int, window_s: int) -> None:
    r = _get_redis()
    if r is None:
        _fallback.hit(key, limit=limit, window_s=window_s)
        return
    try:
        await r.hit_async(key, limit=limit, window_s=window_s)
    except RateLimitExceeded:
        raise
    except Exception as e:  # pragma: no cover
        log.warning("rate_limit: redis hit failed (%s); falling back", e)
        _fallback.hit(key, limit=limit, window_s=window_s)


def reset_for_tests() -> None:
    """Clear the in-process fallback bucket — test helper only."""
    _fallback._buckets.clear()
