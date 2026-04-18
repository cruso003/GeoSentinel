"""PSI drift tests (Phase 2.4 §3)."""

from __future__ import annotations

import random

import pytest

from app.services import drift


def test_psi_zero_on_identical_samples():
    rng = random.Random(42)
    a = [rng.gauss(0, 1) for _ in range(500)]
    # Copy — perfectly identical samples should report ~0.
    assert drift.psi(a, list(a)) == pytest.approx(0.0, abs=1e-9)


def test_psi_rises_with_shift():
    rng = random.Random(123)
    ref = [rng.gauss(0, 1) for _ in range(500)]
    minor = [rng.gauss(0.3, 1) for _ in range(500)]
    major = [rng.gauss(1.5, 1) for _ in range(500)]
    p_minor = drift.psi(ref, minor)
    p_major = drift.psi(ref, major)
    assert p_minor > 0.0
    assert p_major > p_minor
    assert p_major > 0.2  # industry "drift" threshold


def test_psi_handles_empty_sides():
    assert drift.psi([1.0, 2.0], []) == 0.0
    assert drift.psi([], [1.0, 2.0]) == 0.0


def test_psi_report_filters_to_shared_features():
    ref = {"a": [0.0, 1.0, 2.0], "b": [1.0, 1.0, 1.0]}
    cur = {"a": [0.0, 1.0, 2.0], "c": [5.0, 6.0]}
    out = drift.psi_report(ref, cur)
    assert set(out.keys()) == {"a"}


def test_psi_stable_on_degenerate_reference():
    # All-constant reference shouldn't blow up — smoothing keeps log finite.
    ref = [1.0] * 100
    cur = [1.0, 2.0, 3.0, 4.0]
    p = drift.psi(ref, cur)
    assert p >= 0.0
