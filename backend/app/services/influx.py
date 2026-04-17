"""InfluxDB write + query helpers.

Phase 1: all methods are tolerant to the DB being unavailable and fall back to
an in-memory ring buffer so the API still functions in local dev without Influx.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

try:
    from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
    from influxdb_client import Point
    from influxdb_client.client.write_api import ASYNCHRONOUS
except Exception:  # pragma: no cover - optional at startup
    InfluxDBClientAsync = None  # type: ignore[assignment]
    Point = None  # type: ignore[assignment]
    ASYNCHRONOUS = None  # type: ignore[assignment]

from ..core.config import get_settings

# In-memory fallback keyed by (measurement, node_id).
_mem: Dict[tuple[str, str], Deque[dict]] = defaultdict(lambda: deque(maxlen=20_000))


class InfluxService:
    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._connected = False

    async def connect(self) -> None:
        if InfluxDBClientAsync is None:
            return
        s = get_settings()
        try:
            self._client = InfluxDBClientAsync(
                url=s.influxdb_url, token=s.influxdb_token, org=s.influxdb_org
            )
            # cheap ping
            await self._client.ping()
            self._connected = True
        except Exception:
            self._connected = False

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass

    async def write_env(self, reading: dict) -> None:
        self._write_mem("env", reading)
        if not self._connected or Point is None:
            return
        s = get_settings()
        p = (
            Point("env")
            .tag("node_id", reading["node_id"])
            .tag("site_id", reading["site_id"])
            .time(reading["timestamp"])
        )
        for k in ("ph", "turbidity", "dissolved_oxygen", "conductivity", "temperature",
                  "pm25", "pm10", "so2", "no2", "noise_db"):
            v = reading.get(k)
            if v is not None:
                p = p.field(k, float(v))
        write_api = self._client.write_api()
        await write_api.write(bucket=s.influxdb_bucket, record=p)

    async def write_geo(self, reading: dict) -> None:
        self._write_mem("geo", reading)
        if not self._connected or Point is None:
            return
        s = get_settings()
        p = (
            Point("geo")
            .tag("node_id", reading["node_id"])
            .tag("site_id", reading["site_id"])
            .time(reading["timestamp"])
        )
        for k in ("tilt_x", "tilt_y", "crack_displacement", "pore_pressure",
                  "seismic_magnitude", "rainfall_mm"):
            v = reading.get(k)
            if v is not None:
                p = p.field(k, float(v))
        if "seismic_event" in reading:
            p = p.field("seismic_event", bool(reading["seismic_event"]))
        write_api = self._client.write_api()
        await write_api.write(bucket=s.influxdb_bucket, record=p)

    def _write_mem(self, measurement: str, reading: dict) -> None:
        key = (measurement, reading["node_id"])
        r = dict(reading)
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].astimezone(timezone.utc).isoformat()
        _mem[key].append(r)

    async def latest(self, measurement: str, node_id: str) -> Optional[dict]:
        buf = _mem.get((measurement, node_id))
        if not buf:
            return None
        return buf[-1]

    async def history(
        self,
        measurement: str,
        node_id: str,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        buf = _mem.get((measurement, node_id)) or deque()
        out: List[dict] = []
        for r in buf:
            ts = r.get("timestamp")
            t = ts if isinstance(ts, datetime) else datetime.fromisoformat(ts)
            if start <= t <= end:
                out.append(r)
        return out


influx = InfluxService()
