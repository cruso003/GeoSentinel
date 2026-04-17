"""Refresh-token revocation list (Phase 2.1 §8).

A revoked JTI is stored with TTL = remaining token lifetime. When a token
is verified, we check the blocklist and reject on hit. Redis-backed in
production; in-process dict fallback for tests and offline dev.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

try:  # Optional: Redis may be absent.
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore

from ..core.config import get_settings

log = logging.getLogger(__name__)

_KEY_PREFIX = "gs:revoked:"


class _InProcessBlocklist:
    def __init__(self) -> None:
        self._expiry: Dict[str, float] = {}

    def _sweep(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if exp <= now]
        for k in expired:
            self._expiry.pop(k, None)

    def revoke(self, jti: str, ttl_s: int) -> None:
        if ttl_s <= 0:
            return
        self._expiry[jti] = time.time() + ttl_s

    def is_revoked(self, jti: str) -> bool:
        self._sweep()
        return jti in self._expiry


_fallback = _InProcessBlocklist()
_redis_client = None
_redis_tried = False


def _get_redis():
    global _redis_client, _redis_tried
    if _redis_client is not None or _redis_tried:
        return _redis_client
    _redis_tried = True
    if aioredis is None:
        return None
    try:
        _redis_client = aioredis.from_url(
            get_settings().redis_url, encoding="utf-8", decode_responses=True
        )
    except Exception as e:  # pragma: no cover
        log.warning("token_blocklist: redis unavailable (%s); using in-process fallback", e)
        _redis_client = None
    return _redis_client


async def revoke(jti: str, ttl_s: int) -> None:
    if not jti or ttl_s <= 0:
        return
    r = _get_redis()
    if r is None:
        _fallback.revoke(jti, ttl_s)
        return
    try:
        await r.setex(_KEY_PREFIX + jti, ttl_s, "1")
    except Exception as e:  # pragma: no cover
        log.warning("token_blocklist: redis setex failed (%s); falling back", e)
        _fallback.revoke(jti, ttl_s)


async def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    r = _get_redis()
    if r is None:
        return _fallback.is_revoked(jti)
    try:
        return await r.exists(_KEY_PREFIX + jti) > 0
    except Exception as e:  # pragma: no cover
        log.warning("token_blocklist: redis exists failed (%s); falling back", e)
        return _fallback.is_revoked(jti)


def reset_for_tests() -> None:
    global _redis_client, _redis_tried
    _fallback._expiry.clear()
    _redis_client = None
    _redis_tried = False


def remaining_ttl_s(payload: dict) -> int:
    exp = payload.get("exp")
    if not exp:
        return 0
    return max(0, int(exp - time.time()))
