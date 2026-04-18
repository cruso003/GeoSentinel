"""Escalation helpers (Phase 2.3 §5). Pure-function tests — the Celery sweep
itself needs a live DB + mocked notifications, which the integration suite
exercises."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from app.services.escalation import (
    ESCALATION_DWELL,
    ESCALATION_SEVERITIES,
    _current_hop,
    _hop_marker,
)


def test_hop_marker_format():
    assert _hop_marker(1) == "[esc:1]"
    assert _hop_marker(42) == "[esc:42]"


def test_current_hop_empty():
    assert _current_hop(None) == 0
    assert _current_hop("") == 0
    assert _current_hop("operator looking into it") == 0


def test_current_hop_single_marker():
    assert _current_hop("acknowledged at hop [esc:1]") == 1


def test_current_hop_picks_latest_marker():
    notes = "first note [esc:1] more [esc:2] yet more [esc:3]"
    assert _current_hop(notes) == 3


def test_current_hop_ignores_garbled():
    assert _current_hop("[esc:abc] [esc:2] [esc:]") == 2


def test_dwell_is_five_minutes():
    assert ESCALATION_DWELL.total_seconds() == 5 * 60


def test_severities_include_critical_and_evacuation():
    assert set(ESCALATION_SEVERITIES) == {"CRITICAL", "EVACUATION"}
