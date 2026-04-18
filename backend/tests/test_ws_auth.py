"""WebSocket auth guard (Phase 2.1 §6).

The `/ws/{site_id}` endpoint must reject connections that don't present a
valid access-type JWT via `?token=` or the `bearer,<token>` subprotocol.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, create_refresh_token
from app.main import _extract_ws_token, app


def _make_ws(query: str = "", headers: dict | None = None) -> WebSocket:
    scope = {
        "type": "websocket",
        "path": "/ws/site-1",
        "query_string": query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }

    async def _recv():  # pragma: no cover
        return {"type": "websocket.connect"}

    async def _send(_):  # pragma: no cover
        return None

    return WebSocket(scope, receive=_recv, send=_send)


def test_extract_ws_token_from_query():
    ws = _make_ws(query="token=abc.def.ghi")
    assert _extract_ws_token(ws) == "abc.def.ghi"


def test_extract_ws_token_from_subprotocol():
    ws = _make_ws(headers={"sec-websocket-protocol": "bearer, my.token.value"})
    assert _extract_ws_token(ws) == "my.token.value"


def test_extract_ws_token_missing():
    ws = _make_ws()
    assert _extract_ws_token(ws) is None


def test_ws_endpoint_rejects_missing_token():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect("/ws/site-1"):
                pass
        assert ei.value.code == 1008


def test_ws_endpoint_rejects_bad_token():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect("/ws/site-1?token=not-a-jwt"):
                pass
        assert ei.value.code == 1008


def test_ws_endpoint_rejects_refresh_token():
    refresh = create_refresh_token("user-1")
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect(f"/ws/site-1?token={refresh}"):
                pass
        assert ei.value.code == 1008


def test_ws_endpoint_accepts_valid_access_token():
    access = create_access_token("user-1", "operator")
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/site-1?token={access}") as ws:
            # The connection handshake succeeded — we don't exchange messages.
            ws.close()
