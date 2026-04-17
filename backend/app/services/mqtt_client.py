"""MQTT subscriber stub (Phase 2 activation).

In Phase 1 the broker connection is not opened. In Phase 2, subscribe to
    sites/{site_id}/env
    sites/{site_id}/geo
and write each payload to InfluxDB + relay via WebSocket hub.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

try:
    import paho.mqtt.client as mqtt
except Exception:  # pragma: no cover
    mqtt = None  # type: ignore[assignment]

from ..core.config import get_settings
from .influx import influx
from .ws_hub import hub

log = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self) -> None:
        self._client: Optional[object] = None
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        if mqtt is None:
            log.info("paho-mqtt not available; skipping MQTT subscriber.")
            return
        settings = get_settings()
        self._loop = asyncio.get_running_loop()

        def on_connect(client, userdata, flags, rc):  # noqa: ARG001
            log.info("MQTT connected rc=%s", rc)
            client.subscribe("sites/+/env")
            client.subscribe("sites/+/geo")

        def on_message(client, userdata, msg):  # noqa: ARG001
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                return
            kind = "env" if msg.topic.endswith("/env") else "geo"
            site_id = msg.topic.split("/")[1]
            coro = self._handle_payload(site_id, kind, payload)
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(coro, self._loop)

        client = mqtt.Client(client_id="geosentinel-backend")
        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=30)
            client.loop_start()
            self._client = client
            log.info("MQTT subscriber started.")
        except Exception as e:  # pragma: no cover
            log.warning("MQTT broker unreachable: %s", e)

    async def _handle_payload(self, site_id: str, kind: str, payload: dict) -> None:
        if kind == "env":
            await influx.write_env(payload)
        else:
            await influx.write_geo(payload)
        await hub.broadcast(site_id, {"type": "SENSOR_UPDATE", "data": payload})

    async def stop(self) -> None:
        if self._client is not None and mqtt is not None:
            try:
                self._client.loop_stop()  # type: ignore[attr-defined]
                self._client.disconnect()  # type: ignore[attr-defined]
            except Exception:
                pass


mqtt_client = MQTTClient()
