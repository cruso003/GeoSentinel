"""Refresh-cookie + CSRF helpers (Phase 2.1 §10).

We issue the refresh token as an ``HttpOnly; Secure; SameSite=Lax`` cookie
scoped to ``/api/v1/auth`` so it's never visible to JavaScript and never
sent to unrelated endpoints. A companion non-HttpOnly ``gs_csrf`` cookie
carries a random token that the SPA echoes back in the ``X-CSRF-Token``
header — double-submit defence against CSRF now that credentials ride on
cookies.
"""

from __future__ import annotations

import secrets

from fastapi import Request, Response

from ..core.config import Settings, get_settings


def _secure_flag(settings: Settings) -> bool:
    return settings.is_production


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    max_age = settings.refresh_token_expire_days * 24 * 3600
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=_secure_flag(settings),
        samesite="lax",
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
    )


def issue_csrf_cookie(response: Response) -> str:
    """Mint a random CSRF token and set it as a readable cookie. Returns the token."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=_secure_flag(settings),
        samesite="lax",
        path="/",
    )
    return token


def verify_csrf(request: Request) -> bool:
    """Double-submit check: header token must match cookie token and be non-empty."""
    settings = get_settings()
    cookie = request.cookies.get(settings.csrf_cookie_name)
    header = request.headers.get(settings.csrf_header_name)
    if not cookie or not header:
        return False
    return secrets.compare_digest(cookie, header)


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(get_settings().refresh_cookie_name)
