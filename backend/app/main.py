"""GeoSentinel FastAPI application entrypoint (Spec §5)."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, Response

from .api.health import router as health_router
from .api.v1 import api_router
from .core.config import get_settings
from .core.logging import configure_logging, request_id_var
from .core.security import decode_token
from .services import metrics
from .services.influx import influx
from .services.mqtt_client import mqtt_client
from .services.ws_hub import hub

log = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every HTTP request for log correlation."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = rid
        return response


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
    configure_logging(level="INFO")
    app = FastAPI(
        title="GeoSentinel API",
        version="1.0.0",
        description="AI-powered environmental compliance + geohazard intelligence (Spec v1.0).",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)

    # Phase 2.2 S12: enumerate methods + headers. Wildcards combined with
    # `allow_credentials=True` are ignored by browsers anyway and give a
    # false sense of laxity.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Gateway-API-Key",
            settings.csrf_header_name,
        ],
        expose_headers=["Content-Disposition", "Retry-After"],
        max_age=600,
    )

    app.include_router(api_router)
    app.include_router(health_router, prefix="/health")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @app.get("/metrics", tags=["observability"], include_in_schema=False)
    async def prometheus_metrics() -> PlainTextResponse:
        # Prometheus text exposition format. No auth — scrape from within the
        # private network; the edge nginx config blocks public access.
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

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
