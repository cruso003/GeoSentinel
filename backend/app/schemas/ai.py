from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskTier = Literal["LOW", "ELEVATED", "HIGH", "CRITICAL"]
SlopeAlertTier = Literal["NORMAL", "WATCH", "WARNING", "CRITICAL", "EVACUATION"]
SlopeTrend = Literal["STABLE", "DETERIORATING", "IMPROVING"]


class EnviroGuardPredictionOut(BaseModel):
    site_id: str
    timestamp: datetime
    ph_exceedance_24h: float = Field(ge=0, le=1)
    turbidity_exceedance_24h: float = Field(ge=0, le=1)
    do_exceedance_24h: float = Field(ge=0, le=1)
    conductivity_exceedance_24h: float = Field(ge=0, le=1)
    pm25_exceedance_24h: float = Field(ge=0, le=1)
    ph_exceedance_72h: float = Field(ge=0, le=1)
    turbidity_exceedance_72h: float = Field(ge=0, le=1)
    overall_risk_24h: RiskTier
    overall_risk_72h: RiskTier
    confidence: float = Field(ge=0, le=1)


class SlopeWatchPredictionOut(BaseModel):
    site_id: str
    slope_id: str
    timestamp: datetime
    risk_score: float = Field(ge=0, le=1)
    alert_tier: SlopeAlertTier
    pore_pressure_factor: float = Field(ge=0, le=1)
    tilt_factor: float = Field(ge=0, le=1)
    insar_factor: float = Field(ge=0, le=1)
    rainfall_factor: float = Field(ge=0, le=1)
    trend: SlopeTrend
    trend_rate: float


class InferenceRunRequest(BaseModel):
    site_id: str
