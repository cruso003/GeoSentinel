"""Parse InSAR manifests into per-slope displacement time series.

The Phase-2 pipeline (``ai.slopewatch.insar.pipeline``) drops a
``manifest.json`` under ``GEOSENTINEL_INSAR_DIR/<site_id>/``. Depending
on whether ESA creds + SNAP were available, the manifest is one of:

- ``ok`` — a real BEAM-DIMAP pair; we'd open it with ``snappy`` and
  sample per-slope AOI. Left as a follow-up: Phase-3 ships a stub that
  treats ``displacement_mm_mean`` (from the manifest pair metadata) as
  the site-level signal and projects it onto each slope with a fixed
  per-slope offset derived from the slope id, so the shape on the
  frontend is realistic even without SNAP.
- ``synthetic`` — manifests already contain ``displacement_mm_mean`` on
  the single placeholder pair. We synthesise a 4-scene cadence (Sentinel-1
  revisit is 6 days) and a slope-specific drift.
- any error status — nothing to ingest.

Time-series semantics:

- Each Sentinel-1 scene becomes one point per slope at the scene's
  ``sensing_date``.
- ``displacement_mm`` is the cumulative line-of-sight displacement vs.
  the master scene. Positive = moving toward the satellite (uplift);
  negative = subsidence. Per convention, slope instability typically
  shows up as negative values.
- ``velocity_mm_yr`` is the linear-fit rate across the scenes in the
  manifest. One value written per point (same velocity across the pair
  window — the API consumer takes the latest).

This function is idempotent at the file level: ingest is re-runnable
with the same manifest and will just overwrite the same Influx points
(same measurement + tags + timestamp). In the in-memory fallback each
run appends, but the ring buffer is capped.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.site import MineSlope
from .influx import influx

log = logging.getLogger(__name__)

# Sentinel-1A ascending revisit.
SCENE_CADENCE = timedelta(days=6)
# Stable sample count when the manifest provides fewer scenes than the
# frontend chart needs. Mirrors ``_synthetic_manifest`` in the pipeline.
MIN_SCENES = 6


@dataclass(frozen=True)
class ScenePoint:
    sensing_date: date
    # Line-of-sight displacement vs. master scene, in mm. Negative for
    # descending (subsidence) — this is the sign convention the chart uses.
    displacement_mm: float


@dataclass(frozen=True)
class IngestResult:
    site_id: str
    slopes_written: int
    points_written: int
    status: str  # "ok" | "missing-manifest" | "no-slopes" | "skipped-<status>"


def _manifest_path(root: Path, site_id: str) -> Path:
    return root / site_id / "manifest.json"


def _parse_scenes(manifest: dict) -> list[ScenePoint]:
    """Extract a list of (date, site-mean displacement) from a manifest.

    For ``synthetic`` manifests we synthesise a scene series from the
    single placeholder pair mean. For ``ok`` manifests (real SNAP output)
    we currently reuse the per-pair ``displacement_mm_mean`` when the
    pipeline wrote one — the real BEAM-DIMAP sampler is a follow-up.
    """

    scenes_raw = manifest.get("scenes") or []
    if not scenes_raw:
        return []

    # A single pair carries one mean displacement; when missing, default
    # to 0 mm so the series stays flat rather than inventing drift.
    pair_mean = 0.0
    for pair in manifest.get("pairs") or []:
        if "displacement_mm_mean" in pair:
            pair_mean = float(pair["displacement_mm_mean"])
            break

    # Parse scene dates, newest first; oldest is the master (displacement 0).
    parsed: list[date] = []
    for s in scenes_raw:
        try:
            parsed.append(date.fromisoformat(str(s["sensing_date"])))
        except Exception:  # skip malformed rows, keep going
            continue
    if not parsed:
        return []
    parsed.sort()  # oldest -> newest

    # Pad with the Sentinel-1 cadence if the manifest is sparse; keeps the
    # frontend chart legible even on day-1 of a new site.
    while len(parsed) < MIN_SCENES:
        parsed.insert(0, parsed[0] - SCENE_CADENCE)

    # Cumulative displacement reaches ``pair_mean`` on the latest scene,
    # starts at 0 on the master. Interpolate linearly in between; this is
    # the conventional InSAR presentation (reference = master).
    n = len(parsed)
    out: list[ScenePoint] = []
    for i, d in enumerate(parsed):
        frac = i / (n - 1) if n > 1 else 0.0
        out.append(ScenePoint(sensing_date=d, displacement_mm=round(pair_mean * frac, 3)))
    return out


def _slope_offset_mm(slope_id: str) -> float:
    """Per-slope drift offset so a multi-slope site shows distinct curves.

    Deterministic — different slopes land on different constant biases so
    the cumulative-displacement chart doesn't collapse into a single line.
    Magnitude is bounded (±3 mm) so we don't fabricate alarming motion.
    """

    h = 0
    for ch in slope_id:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    unit = ((h % 1000) / 1000.0) - 0.5  # in [-0.5, 0.5)
    return round(unit * 6.0, 3)


def _fit_velocity_mm_yr(points: Sequence[ScenePoint]) -> float:
    """Least-squares slope of displacement vs. time in mm/yr.

    Phase-3 uses this as the headline velocity badge on the UI and also
    as the driver for ``insar_factor`` in SlopeWatch.
    """

    if len(points) < 2:
        return 0.0
    ref = points[0].sensing_date
    xs = [(p.sensing_date - ref).days / 365.25 for p in points]
    ys = [p.displacement_mm for p in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den <= 0:
        return 0.0
    return round(num / den, 3)


async def _site_slopes(db: AsyncSession, site_id: str) -> list[MineSlope]:
    rows = await db.execute(select(MineSlope).where(MineSlope.site_id == site_id))
    return list(rows.scalars().all())


async def ingest_for_site(
    db: AsyncSession, *, site_id: str, root: Path,
) -> IngestResult:
    """Parse the manifest for ``site_id`` and write per-slope samples.

    Returns a summary. Tolerant to missing manifests / empty slope lists /
    malformed entries — those are reported back via the result status so
    the Celery task can surface them without blowing up the beat.
    """

    manifest_file = _manifest_path(root, site_id)
    if not manifest_file.exists():
        return IngestResult(site_id=site_id, slopes_written=0, points_written=0, status="missing-manifest")
    try:
        manifest = json.loads(manifest_file.read_text())
    except json.JSONDecodeError:
        return IngestResult(site_id=site_id, slopes_written=0, points_written=0, status="malformed-manifest")

    m_status = str(manifest.get("status") or "")
    if m_status not in ("synthetic", "ok"):
        return IngestResult(site_id=site_id, slopes_written=0, points_written=0, status=f"skipped-{m_status or 'unknown'}")

    base_scenes = _parse_scenes(manifest)
    if not base_scenes:
        return IngestResult(site_id=site_id, slopes_written=0, points_written=0, status="empty-scenes")

    slopes = await _site_slopes(db, site_id)
    if not slopes:
        return IngestResult(site_id=site_id, slopes_written=0, points_written=0, status="no-slopes")

    total_points = 0
    for slope in slopes:
        offset = _slope_offset_mm(slope.id)
        slope_scenes = [
            ScenePoint(sensing_date=s.sensing_date, displacement_mm=round(s.displacement_mm + offset, 3))
            for s in base_scenes
        ]
        velocity = _fit_velocity_mm_yr(slope_scenes)
        await _write_series(
            site_id=site_id, slope_id=slope.id, scenes=slope_scenes, velocity=velocity,
        )
        total_points += len(slope_scenes)

    return IngestResult(
        site_id=site_id,
        slopes_written=len(slopes),
        points_written=total_points,
        status="ok",
    )


async def _write_series(
    *, site_id: str, slope_id: str, scenes: Iterable[ScenePoint], velocity: float,
) -> None:
    for point in scenes:
        ts = datetime.combine(point.sensing_date, time(12, 0, tzinfo=timezone.utc))
        await influx.write_insar({
            "slope_id": slope_id,
            "site_id": site_id,
            "timestamp": ts.isoformat(),
            "displacement_mm": point.displacement_mm,
            "velocity_mm_yr": velocity,
        })


# --- velocity -> insar_factor coupling ---------------------------------


# Mapping from linear velocity (|mm/yr|) to the SlopeWatch ``insar_factor``
# contribution. The ladder is loosely calibrated against published InSAR
# early-warning thresholds: 5 mm/yr = nominal, 20 mm/yr = elevated,
# 50 mm/yr = critical. ``insar_factor`` is a 0-1 score that the PINN
# combines with pore-pressure / tilt / rainfall to produce ``risk_score``.
_VELOCITY_LADDER_MM_YR = (
    (5.0, 0.1),
    (10.0, 0.2),
    (20.0, 0.45),
    (50.0, 0.75),
    (math.inf, 1.0),
)


def velocity_to_factor(velocity_mm_yr: float) -> float:
    v = abs(float(velocity_mm_yr))
    for limit, score in _VELOCITY_LADDER_MM_YR:
        if v <= limit:
            return score
    return 1.0


async def latest_velocity_mm_yr(slope_id: str) -> float | None:
    latest = await influx.latest("insar", slope_id)
    if not latest:
        return None
    v = latest.get("velocity_mm_yr")
    return None if v is None else float(v)
