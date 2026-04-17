"""ESA Copernicus Data Space Sentinel-1 search + download client (Spec §11.5).

Uses the OData catalog API and S3-compatible product download endpoints.
Credentials come from env: `ESA_DHUS_USERNAME`, `ESA_DHUS_PASSWORD`.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import httpx

CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
DOWNLOAD_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({id})/$value"


@dataclass
class S1Scene:
    product_id: str
    name: str
    sensing_date: date
    orbit_direction: str  # ASCENDING | DESCENDING
    footprint_wkt: str


def _bbox_wkt(lat: float, lng: float, radius_km: float = 8.0) -> str:
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(0.1, abs(lat) / 90.0 + 0.1))
    return (
        f"POLYGON(({lng - dlng} {lat - dlat},"
        f"{lng + dlng} {lat - dlat},"
        f"{lng + dlng} {lat + dlat},"
        f"{lng - dlng} {lat + dlat},"
        f"{lng - dlng} {lat - dlat}))"
    )


async def _access_token(client: httpx.AsyncClient) -> str:
    user = os.environ.get("ESA_DHUS_USERNAME")
    pw = os.environ.get("ESA_DHUS_PASSWORD")
    if not (user and pw):
        raise RuntimeError("ESA Copernicus credentials not configured.")
    resp = await client.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": user,
            "password": pw,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def search_latest(
    *, site_lat: float, site_lng: float, days: int = 14, radius_km: float = 8.0,
) -> list[S1Scene]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    wkt = _bbox_wkt(site_lat, site_lng, radius_km)
    filt = (
        "Collection/Name eq 'SENTINEL-1' "
        "and contains(Name,'IW_SLC') "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') "
        f"and ContentDate/Start ge {since}"
    )
    params = {"$filter": filt, "$orderby": "ContentDate/Start desc", "$top": 20}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(CATALOG_URL, params=params)
        resp.raise_for_status()
        value = resp.json().get("value", [])
    scenes: list[S1Scene] = []
    for entry in value:
        attrs = {a["Name"]: a.get("Value") for a in entry.get("Attributes", [])}
        scenes.append(S1Scene(
            product_id=entry["Id"],
            name=entry["Name"],
            sensing_date=datetime.fromisoformat(entry["ContentDate"]["Start"].replace("Z", "+00:00")).date(),
            orbit_direction=str(attrs.get("orbitDirection", "UNKNOWN")),
            footprint_wkt=entry.get("Footprint", ""),
        ))
    return scenes


async def download_scene(scene: S1Scene, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{scene.name}.zip"
    async with httpx.AsyncClient(timeout=60 * 30, follow_redirects=True) as client:
        token = await _access_token(client)
        url = DOWNLOAD_URL.format(id=scene.product_id)
        async with client.stream("GET", url, headers={"Authorization": f"Bearer {token}"}) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    fh.write(chunk)
    return dest


def ensure_snap_available() -> bool:
    """Return True if the `gpt` (SNAP) binary is on PATH."""
    return shutil.which("gpt") is not None
