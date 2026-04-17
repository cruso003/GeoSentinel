from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EnvSensorReading(BaseModel):
    node_id: str
    site_id: str
    timestamp: datetime
    ph: Optional[float] = None
    turbidity: Optional[float] = None
    dissolved_oxygen: Optional[float] = None
    conductivity: Optional[float] = None
    temperature: Optional[float] = None
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    so2: Optional[float] = None
    no2: Optional[float] = None
    noise_db: Optional[float] = None


class GeoSensorReading(BaseModel):
    node_id: str
    site_id: str
    timestamp: datetime
    tilt_x: Optional[float] = None
    tilt_y: Optional[float] = None
    crack_displacement: Optional[float] = None
    pore_pressure: Optional[float] = None
    seismic_event: bool = False
    seismic_magnitude: Optional[float] = None
    rainfall_mm: Optional[float] = None


class SensorIngestPayload(BaseModel):
    """Wrapper accepted by /sensors/ingest. Mixed env/geo readings welcome."""

    env: list[EnvSensorReading] = Field(default_factory=list)
    geo: list[GeoSensorReading] = Field(default_factory=list)


Resolution = Literal["raw", "5m", "1h", "1d"]
