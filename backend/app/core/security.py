"""JWT issuance and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds bcrypt's 72-byte hard limit."""


def _guard_length(plain: str) -> None:
    limit = get_settings().max_password_bytes
    if len(plain.encode("utf-8")) > limit:
        raise PasswordTooLongError(
            f"Password must be at most {limit} bytes (bcrypt truncates beyond this)."
        )


def hash_password(plain: str) -> str:
    _guard_length(plain)
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > get_settings().max_password_bytes:
        return False
    return _pwd_ctx.verify(plain, hashed)


def _encode(data: dict, expires_delta: timedelta) -> str:
    settings = get_settings()
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(sub: str, role: str) -> str:
    settings = get_settings()
    return _encode(
        {"sub": sub, "role": role, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(sub: str) -> str:
    settings = get_settings()
    return _encode(
        {"sub": sub, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
