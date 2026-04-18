"""Model-registry gate tests (Phase 2.4 §5).

The ``evaluate_gate`` function is pure — we hit it directly rather than
through the API + DB. The registry write-path + audit hook are covered
by smoke-tests that mock the AsyncSession, mirroring the pattern used
in ``test_notifications.py`` / ``test_escalation.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import model_registry as mr

# --- Pure gate logic --------------------------------------------------


def test_first_ever_promotion_passes_unconditionally():
    g = mr.evaluate_gate({"roc_auc": 0.5}, incumbent=None)
    assert g.passed is True
    assert "first-ever" in g.reasons[0]


def test_gate_rejects_auc_regression():
    g = mr.evaluate_gate(
        {"roc_auc": 0.80, "pr_auc": 0.70},
        {"roc_auc": 0.85, "pr_auc": 0.70},
    )
    assert g.passed is False
    assert any("roc_auc" in r for r in g.reasons)


def test_gate_accepts_auc_improvement():
    g = mr.evaluate_gate(
        {"roc_auc": 0.86, "pr_auc": 0.72},
        {"roc_auc": 0.85, "pr_auc": 0.70},
    )
    assert g.passed is True


def test_gate_flags_pr_auc_regression_over_two_percent():
    # 0.70 -> 0.65 is a 5 % drop; threshold is 2 %.
    g = mr.evaluate_gate(
        {"roc_auc": 0.86, "pr_auc": 0.65},
        {"roc_auc": 0.85, "pr_auc": 0.70},
    )
    assert g.passed is False
    assert any("pr_auc" in r for r in g.reasons)


def test_gate_allows_pr_auc_regression_within_band():
    # 0.70 -> 0.685 is 1.5 %, inside the 2 % band.
    g = mr.evaluate_gate(
        {"roc_auc": 0.86, "pr_auc": 0.685},
        {"roc_auc": 0.85, "pr_auc": 0.70},
    )
    assert g.passed is True


def test_gate_catches_slice_regression():
    g = mr.evaluate_gate(
        {
            "roc_auc": 0.86,
            "pr_auc": 0.72,
            "slice_aucs": {"ENV-01": 0.80, "ENV-02": 0.60},
        },
        {
            "roc_auc": 0.85,
            "pr_auc": 0.70,
            "slice_aucs": {"ENV-01": 0.82, "ENV-02": 0.75},
        },
    )
    assert g.passed is False
    assert any("ENV-02" in r for r in g.reasons)


def test_gate_requires_candidate_roc_auc():
    g = mr.evaluate_gate({"pr_auc": 0.7}, {"roc_auc": 0.8, "pr_auc": 0.7})
    assert g.passed is False
    assert "missing roc_auc" in g.reasons[0]


# --- Promote flow (mocked session) ------------------------------------


def _mock_db_with_incumbent(incumbent):
    """Return an AsyncMock session whose ``.execute(...)`` resolves to
    an object with ``.scalar_one_or_none()`` returning ``incumbent`` the
    first call (production lookup) and then the latest-audit-hash (None
    or a row) on subsequent calls. Good enough for the two code paths
    we care about."""

    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.get = AsyncMock()

    class _Scalar:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    # First call: get_production → incumbent. All subsequent calls
    # (audit latest hash) → None.
    db.execute.side_effect = [_Scalar(incumbent)] + [_Scalar(None)] * 5
    return db


@pytest.mark.asyncio
async def test_promote_records_rejection_when_gate_fails():
    from app.models.model_version import ModelVersion

    incumbent = MagicMock(spec=ModelVersion)
    incumbent.id = "inc"
    incumbent.name = "enviroguard"
    incumbent.version = "v1"
    incumbent.metrics_json = '{"roc_auc": 0.90, "pr_auc": 0.85}'
    incumbent.stage = "production"

    candidate = MagicMock(spec=ModelVersion)
    candidate.id = "cand"
    candidate.name = "enviroguard"
    candidate.version = "v2"
    candidate.metrics_json = '{"roc_auc": 0.70, "pr_auc": 0.60}'
    candidate.stage = "candidate"
    candidate.promoted_at = None
    candidate.promoted_by = None

    user = MagicMock()
    user.email = "admin@geosentinel.dev"
    user.role = "esg_admin"

    db = _mock_db_with_incumbent(incumbent)
    result = await mr.promote(db, version=candidate, user=user)

    assert result["promoted"] is False
    assert result["gate"]["passed"] is False
    # Rejected — candidate stays in candidate stage, incumbent keeps
    # production.
    assert candidate.stage == "candidate"
    assert incumbent.stage == "production"


@pytest.mark.asyncio
async def test_promote_rotates_incumbent_when_gate_passes():
    from app.models.model_version import ModelVersion

    incumbent = MagicMock(spec=ModelVersion)
    incumbent.id = "inc"
    incumbent.name = "enviroguard"
    incumbent.version = "v1"
    incumbent.metrics_json = '{"roc_auc": 0.80, "pr_auc": 0.70}'
    incumbent.stage = "production"

    candidate = MagicMock(spec=ModelVersion)
    candidate.id = "cand"
    candidate.name = "enviroguard"
    candidate.version = "v2"
    candidate.metrics_json = '{"roc_auc": 0.86, "pr_auc": 0.72}'
    candidate.stage = "candidate"
    candidate.promoted_at = None
    candidate.promoted_by = None

    user = MagicMock()
    user.email = "admin@geosentinel.dev"
    user.role = "esg_admin"

    db = _mock_db_with_incumbent(incumbent)
    result = await mr.promote(db, version=candidate, user=user)

    assert result["promoted"] is True
    assert candidate.stage == "production"
    assert incumbent.stage == "archived"
    assert candidate.promoted_by == "admin@geosentinel.dev"


@pytest.mark.asyncio
async def test_force_promote_overrides_gate_but_audits_as_forced():
    from app.models.model_version import ModelVersion

    incumbent = MagicMock(spec=ModelVersion)
    incumbent.id = "inc"
    incumbent.name = "enviroguard"
    incumbent.version = "v1"
    incumbent.metrics_json = '{"roc_auc": 0.90}'
    incumbent.stage = "production"

    candidate = MagicMock(spec=ModelVersion)
    candidate.id = "cand"
    candidate.name = "enviroguard"
    candidate.version = "v2"
    candidate.metrics_json = '{"roc_auc": 0.50}'
    candidate.stage = "candidate"
    candidate.promoted_at = None
    candidate.promoted_by = None

    user = MagicMock()
    user.email = "admin@geosentinel.dev"
    user.role = "esg_admin"

    db = _mock_db_with_incumbent(incumbent)
    result = await mr.promote(db, version=candidate, user=user, force=True)

    assert result["promoted"] is True
    assert result["gate"]["passed"] is False
    assert candidate.stage == "production"
