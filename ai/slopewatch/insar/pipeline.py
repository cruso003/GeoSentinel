"""End-to-end Sentinel-1 InSAR pipeline for a mine AOI (Spec §11.5).

Produces `insar_displacement_mm` per slope polygon per acquisition pair. The
resulting timeseries is fed into the SlopeWatch PINN as `insar_factor`.

Usage (operator):
    python -m ai.slopewatch.insar.pipeline \\
        --site tokadeh-liberia --lat 7.535 --lng -8.525 \\
        --out /data/insar/tokadeh

Phase 1 falls back to a synthetic timeseries when SNAP or ESA credentials are
missing; Phase 2 production runs the full graph.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .copernicus import download_scene, ensure_snap_available, search_latest
from .snap_graph import render_graph, run_graph

log = logging.getLogger(__name__)


async def run(
    *, site_id: str, lat: float, lng: float, out_dir: Path, radius_km: float = 8.0,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"site_id": site_id, "scenes": [], "pairs": [], "status": "pending"}

    try:
        scenes = await search_latest(site_lat=lat, site_lng=lng, days=30, radius_km=radius_km)
    except Exception as e:
        log.warning("ESA search failed (%s); writing synthetic placeholder.", e)
        manifest.update(_synthetic_manifest(site_id))
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    manifest["scenes"] = [asdict(s) for s in scenes]
    ascending = [s for s in scenes if s.orbit_direction == "ASCENDING"]
    if len(ascending) < 2:
        manifest["status"] = "insufficient-scenes"
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    master, slave = ascending[0], ascending[1]
    try:
        master_path = await download_scene(master, out_dir / "raw")
        slave_path = await download_scene(slave, out_dir / "raw")
    except Exception as e:
        log.warning("ESA download failed (%s); skipping SNAP run.", e)
        manifest["status"] = "download-failed"
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    if not ensure_snap_available():
        manifest["status"] = "snap-unavailable"
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    output = out_dir / f"{site_id}_ifg.dim"
    aoi = (
        f"POLYGON(({lng - 0.05} {lat - 0.05}, {lng + 0.05} {lat - 0.05}, "
        f"{lng + 0.05} {lat + 0.05}, {lng - 0.05} {lat + 0.05}, "
        f"{lng - 0.05} {lat - 0.05}))"
    )
    xml = render_graph(master=master_path, slave=slave_path, output=output, aoi_wkt=aoi)
    run_graph(xml)

    manifest["pairs"].append({
        "master": master.name,
        "slave": slave.name,
        "output": str(output),
    })
    manifest["status"] = "ok"
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


def _synthetic_manifest(site_id: str) -> dict:
    today = date.today()
    return {
        "site_id": site_id,
        "scenes": [
            {"name": f"SYNTHETIC_{i}", "sensing_date": str(today - timedelta(days=i * 6))}
            for i in range(4)
        ],
        "pairs": [{"master": "SYNTHETIC_0", "slave": "SYNTHETIC_1", "displacement_mm_mean": 0.8}],
        "status": "synthetic",
    }


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser("insar-pipeline")
    parser.add_argument("--site", required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    asyncio.run(run(site_id=args.site, lat=args.lat, lng=args.lng, out_dir=Path(args.out)))


if __name__ == "__main__":
    main()
