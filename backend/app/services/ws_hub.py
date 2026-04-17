"""In-memory WebSocket pub/sub hub.

Spec §5.3 — messages pushed as JSON:
    SENSOR_UPDATE, ALERT_NEW, ALERT_ACKNOWLEDGED, AI_PREDICTION, NODE_STATUS
"""

from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket


class WSHub:
    def __init__(self) -> None:
        self._subs: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, site_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._subs[site_id].add(ws)

    def disconnect(self, site_id: str, ws: WebSocket) -> None:
        self._subs[site_id].discard(ws)

    async def broadcast(self, site_id: str, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._subs[site_id]):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._subs[site_id].discard(ws)


hub = WSHub()
ws_hub = hub  # alias used by routers
