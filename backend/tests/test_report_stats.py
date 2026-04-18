"""ESG compliance report stats (Phase 3 §IFC PDF).

Unit coverage for :func:`collect_compliance_stats` and the PDF renderer.
The DB path is exercised with a mocked ``AsyncSession`` so the test doesn't
need Postgres + a populated fixture set; the renderer smoke-test verifies
that a ``ReportData`` payload produces a non-trivial PDF + stable integrity
hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import report_stats as rs
from app.services.report_generator import generate_report
from app.services.report_stats import (
    MAX_LOG_ROWS,
    REPORTED_PARAMETERS,
    _compliance_pct,
    _expected_samples,
    _limit_label,
    collect_compliance_stats,
)


# --- fakes ------------------------------------------------------------


@dataclass
class _Alert:
    id: str = "a"
    site_id: str = "tokadeh-pilot"
    node_id: str = "ENV-01"
    alert_type: str = "threshold"
    severity: str = "CRITICAL"
    parameter: str = "ph"
    value: float | None = 9.7
    threshold: float | None = 9.0
    message: str = "pH exceeded"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged: bool = False


@dataclass
class _Pred:
    site_id: str = "tokadeh-pilot"
    slope_id: str = "slope-A"
    alert_tier: str = "WARNING"
    risk_score: float = 0.4
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


def _scalars(rows):
    r = MagicMock()
    r.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=list(rows)))
    )
    return r


def _mock_db(alerts, predictions):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalars(alerts), _scalars(predictions)])
    return db


# --- pure helpers -----------------------------------------------------


def test_expected_samples_rounds_up():
    # 12 five-minute samples per hour → 24 h = 288
    assert _expected_samples(timedelta(hours=24)) == 288
    assert _expected_samples(timedelta(minutes=1)) == 1  # always at least 1
    assert _expected_samples(timedelta(0)) == 0


def test_compliance_pct_clamps_between_zero_and_hundred():
    assert _compliance_pct(0, 10) == 100.0
    assert _compliance_pct(5, 10) == 50.0
    assert _compliance_pct(20, 10) == 0.0  # caps at floor
    assert _compliance_pct(1, 0) == 100.0  # degenerate window


def test_limit_label_formats_each_axis():
    assert _limit_label("ph") == "6.0-9.0 pH"
    assert _limit_label("turbidity").startswith("≤")
    assert _limit_label("dissolved_oxygen").startswith("≥")
    assert _limit_label("not-a-parameter") == "—"


# --- collect_compliance_stats ----------------------------------------


@pytest.mark.asyncio
async def test_collect_stats_groups_by_parameter_and_counts_severity():
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 3, 31, tzinfo=UTC)
    # Two CRITICAL pH breaches, one WARNING turbidity (doesn't count as
    # exceedance), one CRITICAL geohazard on slope.
    alerts = [
        _Alert(id="1", parameter="ph", severity="CRITICAL", value=9.8),
        _Alert(id="2", parameter="ph", severity="CRITICAL", value=9.4),
        _Alert(id="3", parameter="turbidity", severity="WARNING", value=4.9),
        _Alert(
            id="4",
            parameter="slope_risk",
            severity="CRITICAL",
            alert_type="geohazard",
            node_id="slope-A",
        ),
    ]
    preds = [_Pred(alert_tier="CRITICAL", risk_score=0.72)]
    db = _mock_db(alerts, preds)

    data = await collect_compliance_stats(
        db, site_id="tokadeh-pilot", period_start=start, period_end=end
    )

    # pH row has 2 exceedances, turbidity row has 0 (WARNING didn't count)
    by_param = {r.parameter: r for r in data.stats_rows}
    assert by_param["ph"].events == 2
    assert by_param["turbidity"].events == 0
    assert by_param["conductivity"].events == 0

    # Exceedance log only contains CRITICAL/EVACUATION rows
    assert {r.parameter for r in data.exceedance_log} == {"ph", "slope_risk"}
    # All three exceedances counted in total
    assert data.exceedance_count == 3
    # Geohazard summary picked up the single slope prediction
    assert data.geohazard.worst_tier == "CRITICAL"
    assert data.geohazard.max_risk_score == 0.72
    assert data.geohazard.critical_events == 1
    assert data.geohazard.slope_predictions_count == 1


@pytest.mark.asyncio
async def test_collect_stats_empty_period_is_fully_compliant():
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 3, 31, tzinfo=UTC)
    db = _mock_db([], [])
    data = await collect_compliance_stats(
        db, site_id="tokadeh-pilot", period_start=start, period_end=end
    )
    assert data.total_alerts == 0
    assert data.exceedance_count == 0
    assert all(r.events == 0 for r in data.stats_rows)
    # Each row with zero exceedances is 100 % compliant
    assert all(r.compliant_pct == 100.0 for r in data.stats_rows)
    # And they all use the em-dash placeholder for mean/max
    assert all(r.mean == "—" for r in data.stats_rows)


@pytest.mark.asyncio
async def test_collect_stats_caps_exceedance_log_length():
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 3, 31, tzinfo=UTC)
    alerts = [
        _Alert(id=str(i), parameter="ph", severity="CRITICAL", value=9.9 - 0.01 * i)
        for i in range(MAX_LOG_ROWS + 10)
    ]
    db = _mock_db(alerts, [])
    data = await collect_compliance_stats(
        db, site_id="tokadeh-pilot", period_start=start, period_end=end
    )
    assert len(data.exceedance_log) == MAX_LOG_ROWS
    # Total exceedance count is not truncated — only the rendered log is.
    assert data.exceedance_count == MAX_LOG_ROWS + 10


def test_reported_parameters_cover_core_ifc_axes():
    # Guardrail: renaming a parameter in thresholds should not silently drop
    # it from the report. Keep this test in sync with the PDF table.
    assert "ph" in REPORTED_PARAMETERS
    assert "turbidity" in REPORTED_PARAMETERS
    assert "pm25" in REPORTED_PARAMETERS


# --- PDF renderer -----------------------------------------------------


def test_generate_report_renders_non_empty_pdf_and_stable_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "REPORTED_PARAMETERS", rs.REPORTED_PARAMETERS)
    # Write into a tmp dir rather than /tmp/geosentinel-reports.
    from app.services import report_generator

    monkeypatch.setattr(report_generator, "REPORTS_DIR", tmp_path)
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 3, 31, tzinfo=UTC)

    path, integrity = generate_report(
        report_id="r1",
        site_name="TokadehTest",
        period_start=start,
        period_end=end,
        report_type="IFC_PERFORMANCE",
    )
    assert path.exists()
    assert path.stat().st_size > 1000  # sanity — a real PDF header + body
    assert len(integrity) == 64

    # Deterministic when inputs are identical.
    _, integrity2 = generate_report(
        report_id="r2",
        site_name="TokadehTest",
        period_start=start,
        period_end=end,
        report_type="IFC_PERFORMANCE",
    )
    assert integrity == integrity2
