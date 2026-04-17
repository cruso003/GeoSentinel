"""Refresh-cookie + CSRF helpers (Phase 2.1 §10)."""

import pytest

pytest.importorskip("fastapi")

from fastapi import Request, Response

from app.core.config import get_settings
from app.services import cookies


def _make_request(cookie_header: str = "", headers: dict | None = None) -> Request:
    raw_headers = []
    if cookie_header:
        raw_headers.append((b"cookie", cookie_header.encode()))
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode(), v.encode()))
    scope = {
        "type": "http",
        "headers": raw_headers,
        "method": "POST",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def test_read_refresh_cookie_returns_none_when_absent():
    req = _make_request()
    assert cookies.read_refresh_cookie(req) is None


def test_read_refresh_cookie_returns_value():
    name = get_settings().refresh_cookie_name
    req = _make_request(cookie_header=f"{name}=abc.def.ghi; other=1")
    assert cookies.read_refresh_cookie(req) == "abc.def.ghi"


def test_verify_csrf_rejects_when_cookie_missing():
    header_name = get_settings().csrf_header_name
    req = _make_request(headers={header_name: "tok"})
    assert cookies.verify_csrf(req) is False


def test_verify_csrf_rejects_when_header_missing():
    name = get_settings().csrf_cookie_name
    req = _make_request(cookie_header=f"{name}=tok")
    assert cookies.verify_csrf(req) is False


def test_verify_csrf_rejects_when_mismatched():
    settings = get_settings()
    req = _make_request(
        cookie_header=f"{settings.csrf_cookie_name}=cookie-tok",
        headers={settings.csrf_header_name: "header-tok"},
    )
    assert cookies.verify_csrf(req) is False


def test_verify_csrf_accepts_matching_token():
    settings = get_settings()
    req = _make_request(
        cookie_header=f"{settings.csrf_cookie_name}=same-value",
        headers={settings.csrf_header_name: "same-value"},
    )
    assert cookies.verify_csrf(req) is True


def test_set_refresh_cookie_is_httponly_and_scoped():
    resp = Response()
    cookies.set_refresh_cookie(resp, "refresh.value")
    header = resp.headers.get("set-cookie")
    settings = get_settings()
    assert header is not None
    assert settings.refresh_cookie_name + "=refresh.value" in header
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.lower() or "samesite=lax" in header.lower()
    assert f"Path={settings.refresh_cookie_path}" in header


def test_issue_csrf_cookie_returns_and_sets_token():
    resp = Response()
    tok = cookies.issue_csrf_cookie(resp)
    assert tok
    header = resp.headers.get("set-cookie")
    settings = get_settings()
    assert settings.csrf_cookie_name + "=" + tok in header
    assert "HttpOnly" not in header  # must be readable by the SPA
