from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel


class SensorNodeOut(BaseModel):
    id: str
    site_id: str
    node_type: str
    name: str
    lat: float
    lng: float
    elevation_m: float
    battery_pct: int
    signal_rssi: int
    last_seen: datetime
    status: str
    calibration_due: date

    class Config:
        from_attributes = True


class MineSlopeOut(BaseModel):
    id: str
    site_id: str
    name: str
    geometry: dict[str, Any]
    mesh_vertices: list[list[float]]

    class Config:
        from_attributes = True


class SiteOut(BaseModel):
    id: str
    name: str
    region: str
    country: str
    centroid: dict[str, float]
    boundary: dict[str, Any]
    nodes: list[SensorNodeOut] = []
    slopes: list[MineSlopeOut] = []


class SiteSummary(BaseModel):
    id: str
    name: str
    region: str
    country: str
    centroid: dict[str, float]


class AlertOut(BaseModel):
    id: str
    site_id: str
    node_id: str
    alert_type: str
    severity: str
    parameter: str
    value: Optional[float]
    threshold: Optional[float]
    message: str
    created_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    notes: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    site_id: str
    period_start: datetime
    period_end: datetime
    report_type: str


class ReportOut(BaseModel):
    id: str
    site_id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    status: str
    download_url: Optional[str] = None
    data_integrity_hash: Optional[str] = None
    created_at: datetime
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommunityStatusOut(BaseModel):
    site_id: str
    overall: str
    water: dict
    air: dict
    ground: dict
