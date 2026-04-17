"""Per-gateway credential service (Phase 2.1 §7).

Keys are formatted ``gs_<prefix>_<secret>``:
  - ``prefix``: 12 chars of base32 — indexed column, used to find the row.
  - ``secret``: 32 chars of base32 — bcrypt-hashed at rest.

`authenticate()` looks up the row by prefix, verifies the secret against
the stored hash, confirms the gateway is active, and returns it. Node scope
enforcement is the caller's responsibility via `allowed_nodes()`.
"""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.gateway import SensorGateway

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_PREFIX_LEN = 12
_SECRET_LEN = 32


def _b32(n_chars: int) -> str:
    # 5 bits per char → nearest whole-byte length then trim.
    raw = secrets.token_bytes(((n_chars * 5) // 8) + 1)
    return base64.b32encode(raw).decode("ascii").rstrip("=")[:n_chars].lower()


def mint_key() -> Tuple[str, str, str]:
    """Return ``(plaintext_key, prefix, hashed_secret)``. Plaintext shown once."""
    prefix = _b32(_PREFIX_LEN)
    secret = _b32(_SECRET_LEN)
    plaintext = f"gs_{prefix}_{secret}"
    hashed = _pwd_ctx.hash(secret)
    return plaintext, prefix, hashed


def _split(presented: str) -> Optional[Tuple[str, str]]:
    if not presented or not presented.startswith("gs_"):
        return None
    parts = presented.split("_", 2)
    if len(parts) != 3:
        return None
    _, prefix, secret = parts
    if len(prefix) != _PREFIX_LEN or len(secret) != _SECRET_LEN:
        return None
    return prefix, secret


async def authenticate(db: AsyncSession, presented: str) -> Optional[SensorGateway]:
    parsed = _split(presented)
    if parsed is None:
        return None
    prefix, secret = parsed
    row = (
        await db.execute(select(SensorGateway).where(SensorGateway.key_prefix == prefix))
    ).scalar_one_or_none()
    if row is None or not row.active:
        return None
    if not _pwd_ctx.verify(secret, row.hashed_key):
        return None
    row.last_used_at = datetime.now(timezone.utc)
    return row


def allowed_nodes(gw: SensorGateway) -> Optional[set[str]]:
    """``None`` means unrestricted; otherwise return the allow-list as a set."""
    if gw.allowed_node_ids is None:
        return None
    return set(gw.allowed_node_ids)
