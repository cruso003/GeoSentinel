"""ESA Sentinel-1 InSAR weekly processing (Spec §11.5, §13.2).

Delegates the actual pipeline to `ai.slopewatch.insar.pipeline`, which handles
ESA Copernicus Data Space auth, scene discovery, SNAP graph execution, and
SNAPHU unwrapping. Output lands under `GEOSENTINEL_INSAR_DIR` as a
site-keyed directory tree + manifest.json.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy import select

from ..core.db import SessionLocal
from ..models.site import Site
from .celery_app import celery_app

log = logging.getLogger(__name__)

INSAR_ROOT = Path(os.environ.get("GEOSENTINEL_INSAR_DIR", "/tmp/geosentinel-insar"))


async def _run(site_id: str | None) -> dict:
    try:
        from ai.slopewatch.insar.pipeline import run as run_pipeline
    except Exception as e:
        log.warning("InSAR pipeline module unavailable: %s", e)
        return {"status": "module-missing"}

    from ..services.insar_ingest import ingest_for_site

    async with SessionLocal() as db:
        stmt = select(Site)
        if site_id:
            stmt = stmt.where(Site.id == site_id)
        sites = (await db.execute(stmt)).scalars().all()

    results: list[dict] = []
    for s in sites:
        out = INSAR_ROOT / s.id
        entry: dict = {"site_id": s.id}
        try:
            result = await run_pipeline(
                site_id=s.id, lat=s.centroid_lat, lng=s.centroid_lng, out_dir=out,
            )
            entry["status"] = result.get("status", "unknown")
        except Exception as e:
            log.exception("InSAR pipeline failed for %s: %s", s.id, e)
            entry["status"] = "error"
            entry["error"] = str(e)
            results.append(entry)
            continue

        # Parse the manifest into per-slope Influx points so the PINN and
        # the dashboard can consume a real displacement series on the
        # next SlopeWatch beat. Failures here are non-fatal — the beat
        # succeeded from the producer's perspective.
        try:
            async with SessionLocal() as ingest_db:
                ingest = await ingest_for_site(ingest_db, site_id=s.id, root=INSAR_ROOT)
            entry["ingest"] = {
                "status": ingest.status,
                "slopes_written": ingest.slopes_written,
                "points_written": ingest.points_written,
            }
        except Exception as e:
            log.exception("InSAR ingest failed for %s: %s", s.id, e)
            entry["ingest"] = {"status": "error", "error": str(e)}
        results.append(entry)
    return {"results": results, "count": len(results)}


@celery_app.task(name="app.tasks.insar_processing.process_sentinel1_scene")
def process_sentinel1_scene(site_id: str | None = None) -> dict:
    return asyncio.run(_run(site_id))
