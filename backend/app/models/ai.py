from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class EnviroGuardPrediction(Base):
    __tablename__ = "enviroguard_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    ph_exceedance_24h: Mapped[float] = mapped_column(Float)
    turbidity_exceedance_24h: Mapped[float] = mapped_column(Float)
    do_exceedance_24h: Mapped[float] = mapped_column(Float)
    conductivity_exceedance_24h: Mapped[float] = mapped_column(Float)
    pm25_exceedance_24h: Mapped[float] = mapped_column(Float)
    ph_exceedance_72h: Mapped[float] = mapped_column(Float)
    turbidity_exceedance_72h: Mapped[float] = mapped_column(Float)
    overall_risk_24h: Mapped[str] = mapped_column(String(16))
    overall_risk_72h: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)


class SlopeWatchPrediction(Base):
    __tablename__ = "slopewatch_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"), index=True)
    slope_id: Mapped[str] = mapped_column(String(64), ForeignKey("mine_slopes.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    alert_tier: Mapped[str] = mapped_column(String(16))
    pore_pressure_factor: Mapped[float] = mapped_column(Float)
    tilt_factor: Mapped[float] = mapped_column(Float)
    insar_factor: Mapped[float] = mapped_column(Float)
    rainfall_factor: Mapped[float] = mapped_column(Float)
    trend: Mapped[str] = mapped_column(String(16))
    trend_rate: Mapped[float] = mapped_column(Float)
