"""GeoSentinel FastAPI application entrypoint (Spec §5)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_router
from .core.config import get_settings
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
        await hub.connect(site_id, ws)
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
