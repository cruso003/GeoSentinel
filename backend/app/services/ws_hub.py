"""In-memory WebSocket pub/sub hub.

Spec §5.3 — messages pushed as JSON:
    SENSOR_UPDATE, ALERT_NEW, ALERT_ACKNOWLEDGED, AI_PREDICTION, NODE_STATUS

Phase 2.2 S13: broadcasts fan out concurrently with a per-send timeout.
One slow or wedged client no longer blocks its peers, and the dead-socket
sweep prunes anything that errored or timed out.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

log = logging.getLogger(__name__)

# Per-client send timeout. At our broadcast rate (~1/s per site), a
# laptop on a tethered 3G link should still keep up; anything slower is
# effectively gone and should be dropped rather than back-pressured.
_SEND_TIMEOUT_S = 2.0


class WSHub:
    def __init__(self) -> None:
        self._subs: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(
        self,
        site_id: str,
        ws: WebSocket,
        *,
        subprotocol: Optional[str] = None,
    ) -> None:
        await ws.accept(subprotocol=subprotocol)
        self._subs[site_id].add(ws)

    def disconnect(self, site_id: str, ws: WebSocket) -> None:
        self._subs[site_id].discard(ws)

    def subscriber_count(self, site_id: str) -> int:
        return len(self._subs.get(site_id, set()))

    async def _send_one(self, ws: WebSocket, message: dict[str, Any]) -> Optional[WebSocket]:
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=_SEND_TIMEOUT_S)
            return None
        except asyncio.TimeoutError:
            log.info("ws_hub: send timed out; pruning slow client")
            return ws
        except Exception as e:
            log.debug("ws_hub: send failed (%s); pruning client", e)
            return ws

    async def broadcast(self, site_id: str, message: dict[str, Any]) -> None:
        targets = list(self._subs.get(site_id, set()))
        if not targets:
            return
        results = await asyncio.gather(
            *(self._send_one(ws, message) for ws in targets),
            return_exceptions=False,
        )
        for dead in results:
            if dead is not None:
                self._subs[site_id].discard(dead)


hub = WSHub()
ws_hub = hub  # alias used by routers
