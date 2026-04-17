"""Seed script for Tokadeh pilot site (Spec §15.3).

Usage:
    python -m app.core.seed

Creates:
  - 1 Site: Tokadeh (Nimba County, Liberia)
  - 5 Sensor Nodes: 3 environmental (ENV-01..03), 2 geotechnical (GEO-01..02)
  - 2 Mine Slopes: slope-north-a, slope-tailings-east
  - 3 Users: admin@geosentinel.dev / operator@geosentinel.dev / community@geosentinel.dev
    (all passwords: geosentinel)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from .db import SessionLocal, engine, Base
from .security import hash_password
from ..models.site import MineSlope, SensorNode, Site
from ..models.user import User


TOKADEH_ID = "tokadeh-liberia"


TOKADEH_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[
        [-8.5300, 7.5400],
        [-8.5200, 7.5400],
        [-8.5200, 7.5300],
        [-8.5300, 7.5300],
        [-8.5300, 7.5400],
    ]],
}


def _nodes() -> list[dict]:
    today = date.today()
    cal = today.replace(year=today.year + 1)
    return [
        {"id": "ENV-01", "node_type": "ENVIRONMENTAL", "name": "Water — Upstream",
         "lat": 7.5385, "lng": -8.5285, "elevation_m": 540.0},
        {"id": "ENV-02", "node_type": "ENVIRONMENTAL", "name": "Water — Downstream",
         "lat": 7.5332, "lng": -8.5261, "elevation_m": 512.0},
        {"id": "ENV-03", "node_type": "ENVIRONMENTAL", "name": "Air — Community",
         "lat": 7.5312, "lng": -8.5247, "elevation_m": 498.0},
        {"id": "GEO-01", "node_type": "GEOTECHNICAL", "name": "North Slope Tilt",
         "lat": 7.5372, "lng": -8.5276, "elevation_m": 612.0},
        {"id": "GEO-02", "node_type": "GEOTECHNICAL", "name": "Tailings East Piezometer",
         "lat": 7.5348, "lng": -8.5220, "elevation_m": 556.0},
    ], cal


def _slopes() -> list[dict]:
    return [
        {
            "id": "slope-north-a",
            "name": "North Slope Section A",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-8.5288, 7.5382],
                    [-8.5262, 7.5382],
                    [-8.5262, 7.5362],
                    [-8.5288, 7.5362],
                    [-8.5288, 7.5382],
                ]],
            },
            "mesh_vertices": [
                [0, 0, 40], [10, 0, 38], [20, 0, 35], [30, 0, 32],
                [0, 10, 36], [10, 10, 34], [20, 10, 31], [30, 10, 28],
            ],
        },
        {
            "id": "slope-tailings-east",
            "name": "Tailings East Slope",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-8.5232, 7.5356],
                    [-8.5208, 7.5356],
                    [-8.5208, 7.5334],
                    [-8.5232, 7.5334],
                    [-8.5232, 7.5356],
                ]],
            },
            "mesh_vertices": [
                [0, 0, 28], [12, 0, 26], [24, 0, 23],
                [0, 12, 25], [12, 12, 23], [24, 12, 20],
            ],
        },
    ]


async def seed_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        existing_site = await db.get(Site, TOKADEH_ID)
        if existing_site is None:
            db.add(Site(
                id=TOKADEH_ID,
                name="Tokadeh Iron Ore Mine",
                region="Nimba County",
                country="Liberia",
                centroid_lat=7.5350,
                centroid_lng=-8.5250,
                boundary_geojson=TOKADEH_BOUNDARY,
            ))
            nodes, cal_due = _nodes()
            for n in nodes:
                db.add(SensorNode(
                    id=n["id"],
                    site_id=TOKADEH_ID,
                    node_type=n["node_type"],
                    name=n["name"],
                    lat=n["lat"],
                    lng=n["lng"],
                    elevation_m=n["elevation_m"],
                    battery_pct=92,
                    signal_rssi=-68,
                    last_seen=datetime.now(timezone.utc),
                    status="ONLINE",
                    calibration_due=cal_due,
                ))
            for s in _slopes():
                db.add(MineSlope(
                    id=s["id"],
                    site_id=TOKADEH_ID,
                    name=s["name"],
                    geometry_geojson=s["geometry"],
                    mesh_vertices=s["mesh_vertices"],
                ))

        # Users
        for email, name, role in [
            ("admin@geosentinel.dev", "Henrique Crusoe", "esg_admin"),
            ("operator@geosentinel.dev", "Control Room Operator", "operator"),
            ("community@geosentinel.dev", "Nimba Community Portal", "community"),
        ]:
            exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if exists is None:
                db.add(User(
                    id=str(uuid4()),
                    email=email,
                    name=name,
                    hashed_password=hash_password("geosentinel"),
                    role=role,
                ))

        await db.commit()
    print(f"Seed complete. Site={TOKADEH_ID}, 5 nodes, 2 slopes, 3 users.")


if __name__ == "__main__":
    asyncio.run(seed_all())
