from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(128))
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lng: Mapped[float] = mapped_column(Float)
    boundary_geojson: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    nodes: Mapped[list["SensorNode"]] = relationship(back_populates="site", cascade="all, delete-orphan")
    slopes: Mapped[list["MineSlope"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class SensorNode(Base):
    __tablename__ = "sensor_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"))
    node_type: Mapped[str] = mapped_column(String(16))  # ENVIRONMENTAL | GEOTECHNICAL
    name: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float] = mapped_column(Float, default=0.0)
    battery_pct: Mapped[int] = mapped_column(Integer, default=100)
    signal_rssi: Mapped[int] = mapped_column(Integer, default=-70)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16), default="ONLINE")
    calibration_due: Mapped[date] = mapped_column(Date)

    site: Mapped[Site] = relationship(back_populates="nodes")


class MineSlope(Base):
    __tablename__ = "mine_slopes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    site_id: Mapped[str] = mapped_column(String(64), ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(255))
    geometry_geojson: Mapped[dict] = mapped_column(JSON)
    mesh_vertices: Mapped[list] = mapped_column(JSON)

    site: Mapped[Site] = relationship(back_populates="slopes")
