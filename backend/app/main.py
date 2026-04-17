"""GeoSentinel FastAPI application entrypoint (Spec §5)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_router
from .core.config import get_settings
from .core.security import decode_token
from .services.influx import influx
from .services.mqtt_client import mqtt_client
from .services.ws_hub import hub

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    await influx.connect()
    await mqtt_client.start()
    try:
        yield
    finally:
        await mqtt_client.stop()
        await influx.close()


def _extract_ws_token(ws: WebSocket) -> Optional[str]:
    """Resolve a bearer token from `?token=` or `Sec-WebSocket-Protocol: bearer,<token>`."""
    token = ws.query_params.get("token")
    if token:
        return token
    proto = ws.headers.get("sec-websocket-protocol")
    if proto:
        parts = [p.strip() for p in proto.split(",")]
        if len(parts) >= 2 and parts[0].lower() == "bearer":
            return parts[1]
    return None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="GeoSentinel API",
        version="1.0.0",
        description="AI-powered environmental compliance + geohazard intelligence (Spec v1.0).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @app.websocket("/ws/{site_id}")
    async def websocket_endpoint(ws: WebSocket, site_id: str) -> None:
        # Phase 2.1 §6: require a valid access token. Unauthenticated sockets
        # are the entry point into live sensor/alert streams, so they must
        # never be anonymous in production.
        token = _extract_ws_token(ws)
        payload = decode_token(token) if token else None
        if not payload or payload.get("type") != "access":
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # If the client negotiated `bearer,<token>`, echo back the first
        # subprotocol so the handshake succeeds.
        subprotocol: Optional[str] = None
        proto = ws.headers.get("sec-websocket-protocol")
        if proto and proto.split(",")[0].strip().lower() == "bearer":
            subprotocol = "bearer"

        await hub.connect(site_id, ws, subprotocol=subprotocol)
        try:
            while True:
                # Keep-alive loop; clients may send heartbeats we ignore.
                await ws.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(site_id, ws)
        except Exception:  # pragma: no cover
            hub.disconnect(site_id, ws)

    return app


app = create_app()
