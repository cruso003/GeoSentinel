"""Model-evaluation harness (Phase 2.4 §2).

Computes ROC-AUC, PR-AUC, Brier score, and per-slice breakdowns using only
the stdlib — training hosts (and Celery workers) shouldn't need sklearn to
tell us whether a model is still worth shipping.

Inputs are plain (``y_true`` ∈ {0,1}, ``y_score`` ∈ [0,1]) sequences so the
harness can consume predictions replayed out of the DB without reconstructing
feature tensors. Each metric returns ``None`` when the slice is degenerate
(fewer than one positive and one negative) rather than raising — degenerate
slices are normal during cold-start and we'd rather report a gap than crash
the nightly job.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass
class Metrics:
    n: int
    positives: int
    roc_auc: float | None
    pr_auc: float | None
    brier: float | None
    # Calibration gap at the 0.5 threshold — mean(y_score) - mean(y_true).
    # Useful for spotting models that are systematically over- or under-
    # confident even when AUC looks fine.
    calibration_gap: float | None

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "positives": self.positives,
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "brier": self.brier,
            "calibration_gap": self.calibration_gap,
        }


@dataclass
class SliceReport:
    overall: Metrics
    slices: dict[str, Metrics] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "overall": self.overall.as_dict(),
            "slices": {k: v.as_dict() for k, v in self.slices.items()},
        }


def _roc_auc(y_true: Sequence[int], y_score: Sequence[float]) -> float | None:
    """Mann-Whitney U formulation — equivalent to the ROC integral but
    stable against tied scores (tie -> +0.5)."""

    pos = [s for t, s in zip(y_true, y_score, strict=True) if t == 1]
    neg = [s for t, s in zip(y_true, y_score, strict=True) if t == 0]
    if not pos or not neg:
        return None
    gt = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                gt += 1.0
            elif p == n:
                gt += 0.5
    return gt / (len(pos) * len(neg))


def _pr_auc(y_true: Sequence[int], y_score: Sequence[float]) -> float | None:
    """Average precision — trapezoidal area under the PR curve walked in
    descending-score order."""

    if not y_true:
        return None
    total_pos = sum(y_true)
    if total_pos == 0 or total_pos == len(y_true):
        return None
    pairs = sorted(
        zip(y_score, y_true, strict=True), key=lambda p: p[0], reverse=True
    )
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for _, t in pairs:
        if t == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp)
        recall = tp / total_pos
        if recall > prev_recall:
            area += precision * (recall - prev_recall)
            prev_recall = recall
    return area


def _brier(y_true: Sequence[int], y_score: Sequence[float]) -> float | None:
    if not y_true:
        return None
    return sum((s - t) ** 2 for t, s in zip(y_true, y_score, strict=True)) / len(
        y_true
    )


def _calibration_gap(
    y_true: Sequence[int], y_score: Sequence[float]
) -> float | None:
    if not y_true:
        return None
    return sum(y_score) / len(y_score) - sum(y_true) / len(y_true)


def compute_metrics(
    y_true: Sequence[int], y_score: Sequence[float]
) -> Metrics:
    n = len(y_true)
    positives = sum(y_true) if n else 0
    return Metrics(
        n=n,
        positives=positives,
        roc_auc=_roc_auc(y_true, y_score),
        pr_auc=_pr_auc(y_true, y_score),
        brier=_brier(y_true, y_score),
        calibration_gap=_calibration_gap(y_true, y_score),
    )


def evaluate_with_slices(
    y_true: Sequence[int],
    y_score: Sequence[float],
    slices: Iterable[str] | None = None,
) -> SliceReport:
    """Overall metrics plus one sub-report per slice label (e.g. node_id,
    parameter). ``slices`` must be the same length as ``y_true`` when given —
    a zip'd-together column from the prediction store."""

    overall = compute_metrics(y_true, y_score)
    report = SliceReport(overall=overall)
    if slices is None:
        return report

    buckets: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for label, t, s in zip(slices, y_true, y_score, strict=True):
        buckets[label].append((t, s))
    for label, rows in buckets.items():
        ts = [r[0] for r in rows]
        ss = [r[1] for r in rows]
        report.slices[label] = compute_metrics(ts, ss)
    return report
