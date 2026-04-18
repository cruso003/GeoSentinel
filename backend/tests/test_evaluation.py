"""Evaluation harness tests (Phase 2.4 §2)."""

from __future__ import annotations

import pytest

from app.services import evaluation


def test_roc_auc_perfect_separation():
    m = evaluation.compute_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    assert m.roc_auc == pytest.approx(1.0)
    assert m.pr_auc == pytest.approx(1.0)


def test_roc_auc_reverse_ranking_is_zero():
    # Positives all score below negatives → AUC = 0.
    m = evaluation.compute_metrics([0, 0, 1, 1], [0.8, 0.9, 0.1, 0.2])
    assert m.roc_auc == pytest.approx(0.0)


def test_roc_auc_ties_count_half():
    # All scores tied — every comparison is a tie (+0.5) → AUC = 0.5.
    m = evaluation.compute_metrics([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5])
    assert m.roc_auc == pytest.approx(0.5)


def test_degenerate_slice_returns_none():
    m = evaluation.compute_metrics([1, 1, 1], [0.2, 0.3, 0.9])
    assert m.roc_auc is None
    assert m.pr_auc is None
    # Brier + calibration still defined on one-class data.
    assert m.brier is not None
    assert m.calibration_gap is not None


def test_brier_matches_reference():
    # Hand-computed: ((0.1-0)^2 + (0.9-1)^2 + (0.4-0)^2 + (0.7-1)^2)/4
    expected = (0.01 + 0.01 + 0.16 + 0.09) / 4
    m = evaluation.compute_metrics([0, 1, 0, 1], [0.1, 0.9, 0.4, 0.7])
    assert m.brier == pytest.approx(expected)


def test_calibration_gap_flags_overconfidence():
    # Model predicts 0.9 everywhere but half are negative → gap = +0.4.
    m = evaluation.compute_metrics([0, 0, 1, 1], [0.9, 0.9, 0.9, 0.9])
    assert m.calibration_gap == pytest.approx(0.4)


def test_slice_report_splits_by_label():
    y = [0, 1, 0, 1]
    s = [0.1, 0.9, 0.3, 0.2]
    slices = ["a", "a", "b", "b"]
    r = evaluation.evaluate_with_slices(y, s, slices=slices)
    assert r.overall.n == 4
    assert set(r.slices.keys()) == {"a", "b"}
    # Slice "a": positive (0.9) > negative (0.1) → AUC = 1.
    assert r.slices["a"].roc_auc == pytest.approx(1.0)
    # Slice "b": positive (0.2) < negative (0.3) → AUC = 0.
    assert r.slices["b"].roc_auc == pytest.approx(0.0)


def test_pr_auc_is_monotone_in_ranking_quality():
    good = evaluation.compute_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    mixed = evaluation.compute_metrics([0, 1, 0, 1], [0.2, 0.3, 0.5, 0.9])
    assert good.pr_auc >= mixed.pr_auc


def test_empty_inputs():
    m = evaluation.compute_metrics([], [])
    assert m.n == 0
    assert m.roc_auc is None
    assert m.brier is None
