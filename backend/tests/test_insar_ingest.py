"""InSAR manifest -> per-slope displacement ingestion (Phase 3 §InSAR).

The pipeline writes a manifest.json that lists scenes + pair mean
displacement. ``ingest_for_site`` expands that into a per-slope time
series and writes to Influx (in-memory fallback here). The service is
kept resilient to missing / malformed manifests because it runs as part
of the weekly Celery beat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import influx as influx_mod
from app.services.insar_ingest import (
    MIN_SCENES,
    ScenePoint,
    _fit_velocity_mm_yr,
    _parse_scenes,
    _slope_offset_mm,
    ingest_for_site,
    latest_velocity_mm_yr,
    velocity_to_factor,
)


# --- fakes ------------------------------------------------------------


@dataclass
class _Slope:
    id: str
    site_id: str = "tokadeh-pilot"
    name: str = "slope"


def _scalars(rows):
    r = MagicMock()
    r.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=list(rows)))
    )
    return r


def _mock_db(slopes):
    db = MagicMock()
    db.execute = AsyncMock(return_value=_scalars(slopes))
    return db


def _write_manifest(root: Path, site_id: str, manifest: dict) -> Path:
    d = root / site_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / "manifest.json"
    p.write_text(json.dumps(manifest, default=str))
    return p


@pytest.fixture(autouse=True)
def _reset_mem_buffer():
    """Each test starts with an empty in-process Influx ring buffer so the
    velocity/latest helpers don't read leftover points from a prior test."""
    influx_mod._mem.clear()
    yield
    influx_mod._mem.clear()


# --- helpers ----------------------------------------------------------


def test_velocity_ladder_matches_severity_tiers():
    assert velocity_to_factor(0.0) == 0.1
    assert velocity_to_factor(5.0) == 0.1  # edge: <=5 mm/yr is nominal
    assert velocity_to_factor(10.0) == 0.2
    assert velocity_to_factor(20.0) == 0.45
    assert velocity_to_factor(50.0) == 0.75
    assert velocity_to_factor(120.0) == 1.0
    # Sign-agnostic: subsidence (-mm/yr) is just as dangerous as uplift.
    assert velocity_to_factor(-35.0) == 0.75


def test_fit_velocity_mm_yr_linear_slope():
    start = date(2025, 1, 1)
    pts = [
        ScenePoint(sensing_date=start, displacement_mm=0.0),
        ScenePoint(sensing_date=start + timedelta(days=365), displacement_mm=12.0),
    ]
    assert _fit_velocity_mm_yr(pts) == pytest.approx(12.0, rel=1e-3)


def test_fit_velocity_empty_or_single_point_is_zero():
    assert _fit_velocity_mm_yr([]) == 0.0
    assert _fit_velocity_mm_yr([ScenePoint(sensing_date=date.today(), displacement_mm=5.0)]) == 0.0


def test_slope_offset_is_deterministic_and_bounded():
    a = _slope_offset_mm("slope-alpha")
    b = _slope_offset_mm("slope-alpha")
    c = _slope_offset_mm("slope-beta")
    assert a == b
    assert a != c  # different seed -> different bias
    assert -3.0 <= a <= 3.0


def test_parse_scenes_pads_up_to_min_scenes():
    manifest = {
        "scenes": [{"sensing_date": "2026-04-10"}, {"sensing_date": "2026-04-16"}],
        "pairs": [{"displacement_mm_mean": 2.0}],
    }
    points = _parse_scenes(manifest)
    assert len(points) >= MIN_SCENES
    # Cumulative series: master = 0, newest carries the pair mean.
    assert points[0].displacement_mm == 0.0
    assert points[-1].displacement_mm == pytest.approx(2.0, rel=1e-3)


def test_parse_scenes_handles_missing_pair_mean():
    manifest = {
        "scenes": [{"sensing_date": "2026-01-01"}, {"sensing_date": "2026-01-07"}],
        "pairs": [{"master": "A", "slave": "B"}],  # no displacement_mm_mean
    }
    points = _parse_scenes(manifest)
    assert all(p.displacement_mm == 0.0 for p in points)


def test_parse_scenes_skips_malformed_dates():
    manifest = {
        "scenes": [
            {"sensing_date": "not-a-date"},
            {"sensing_date": "2026-01-01"},
            {"sensing_date": "2026-01-07"},
        ],
        "pairs": [{"displacement_mm_mean": 1.0}],
    }
    points = _parse_scenes(manifest)
    assert len(points) >= MIN_SCENES
    # The malformed entry is dropped; remaining dates still parse.


# --- ingest_for_site --------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_synthetic_manifest_writes_one_series_per_slope(tmp_path):
    manifest = {
        "site_id": "tokadeh-pilot",
        "status": "synthetic",
        "scenes": [
            {"sensing_date": str(date(2026, 3, 1) + timedelta(days=6 * i))}
            for i in range(4)
        ],
        "pairs": [{"master": "SYN_0", "slave": "SYN_3", "displacement_mm_mean": 0.8}],
    }
    _write_manifest(tmp_path, "tokadeh-pilot", manifest)
    db = _mock_db([_Slope(id="slope-A"), _Slope(id="slope-B")])

    result = await ingest_for_site(db, site_id="tokadeh-pilot", root=tmp_path)

    assert result.status == "ok"
    assert result.slopes_written == 2
    # Each slope got at least MIN_SCENES points (padding kicks in).
    assert result.points_written >= MIN_SCENES * 2
    # Latest velocity is now queryable via the Influx helper.
    v_a = await latest_velocity_mm_yr("slope-A")
    v_b = await latest_velocity_mm_yr("slope-B")
    assert v_a is not None and v_b is not None
    # Same manifest -> same fitted velocity shape per slope (offset is a
    # bias, not a slope change), so velocities should match.
    assert v_a == pytest.approx(v_b, rel=1e-6)


@pytest.mark.asyncio
async def test_ingest_missing_manifest_is_soft_error(tmp_path):
    db = _mock_db([_Slope(id="slope-A")])
    result = await ingest_for_site(db, site_id="tokadeh-pilot", root=tmp_path)
    assert result.status == "missing-manifest"
    assert result.slopes_written == 0


@pytest.mark.asyncio
async def test_ingest_manifest_with_error_status_skipped(tmp_path):
    _write_manifest(
        tmp_path,
        "tokadeh-pilot",
        {"site_id": "tokadeh-pilot", "status": "snap-unavailable", "scenes": []},
    )
    db = _mock_db([_Slope(id="slope-A")])
    result = await ingest_for_site(db, site_id="tokadeh-pilot", root=tmp_path)
    assert result.status.startswith("skipped-")
    assert result.points_written == 0


@pytest.mark.asyncio
async def test_ingest_no_slopes_does_not_write(tmp_path):
    _write_manifest(
        tmp_path,
        "tokadeh-pilot",
        {
            "site_id": "tokadeh-pilot",
            "status": "synthetic",
            "scenes": [{"sensing_date": "2026-04-10"}, {"sensing_date": "2026-04-16"}],
            "pairs": [{"displacement_mm_mean": 1.0}],
        },
    )
    db = _mock_db([])  # RBAC-ish: the site has no slopes configured.
    result = await ingest_for_site(db, site_id="tokadeh-pilot", root=tmp_path)
    assert result.status == "no-slopes"


@pytest.mark.asyncio
async def test_ingest_malformed_json_returns_error_status(tmp_path):
    d = tmp_path / "tokadeh-pilot"
    d.mkdir()
    (d / "manifest.json").write_text("{not valid json")
    db = _mock_db([_Slope(id="slope-A")])
    result = await ingest_for_site(db, site_id="tokadeh-pilot", root=tmp_path)
    assert result.status == "malformed-manifest"


# --- latest_velocity_mm_yr -------------------------------------------


@pytest.mark.asyncio
async def test_latest_velocity_reports_none_when_no_points():
    # Clean buffer (autouse fixture), no writes — helper returns None so
    # the SlopeWatch service can fall back to the old heuristic.
    assert await latest_velocity_mm_yr("slope-unknown") is None
