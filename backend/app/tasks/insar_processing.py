"""ESA Sentinel-1 InSAR weekly processing (Spec §11.5, §13.2)."""

from __future__ import annotations

import logging

from .celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.insar_processing.process_sentinel1_scene")
def process_sentinel1_scene(site_id: str | None = None) -> str:
    """Phase 2: download latest S1 SLC, coregister + unwrap via SNAP/snappy.

    Current behaviour is a no-op recording intent so the beat schedule fires
    without error in dev. The real pipeline:
        1. Query ESA Copernicus Data Space for the latest ascending + descending
           acquisitions covering the site bounding box.
        2. TOPSAR-Split + Apply-Orbit-File.
        3. Interferogram formation with the previous acquisition.
        4. Goldstein phase filtering, SNAPHU unwrap.
        5. Extract per-pixel line-of-sight displacement over the slope polygons.
        6. Feed into the SlopeWatch feature pipeline (`insar_displacement_mm`).
    """
    log.info("InSAR processing stub invoked for site=%s", site_id or "<all>")
    return "queued"
