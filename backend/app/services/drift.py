"""Drift monitoring via PSI (Phase 2.4 §3).

Population Stability Index compares a *reference* distribution (what the
model was trained on) to a *current* distribution (what production is now
feeding it). The classic interpretation on quantile-binned inputs:

- ``PSI < 0.1``  — stable.
- ``0.1 ≤ PSI < 0.2`` — minor shift, monitor.
- ``PSI ≥ 0.2``  — material drift, investigate retraining.

We bin on reference quantiles rather than fixed-width bins so comparison
is invariant to the native scale of each feature — rainfall, conductivity,
and slope displacement coexist in the same gauge.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# Smoothing constant. Without this the ``log(current/reference)`` blows up
# when a bin is empty in one side — drift reports full of ``inf`` are
# actively misleading.
_EPS = 1e-4


def _quantile_edges(sample: Sequence[float], bins: int) -> list[float]:
    if len(sample) < bins:
        # Under-sampled — fall back to min/max split. Not great statistically
        # but the alternative is a ZeroDivisionError during cold-start.
        if not sample:
            return [0.0, 1.0]
        lo, hi = min(sample), max(sample)
        if lo == hi:
            hi = lo + 1.0
        step = (hi - lo) / bins
        return [lo + step * i for i in range(bins + 1)]
    ordered = sorted(sample)
    edges = []
    for i in range(bins + 1):
        idx = int(round(i * (len(ordered) - 1) / bins))
        edges.append(ordered[idx])
    # Guarantee a strictly-increasing edge list — ties on a quantile would
    # collapse a bin and divide-by-zero below.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + _EPS
    return edges


def _histogram(sample: Sequence[float], edges: Sequence[float]) -> list[float]:
    counts = [0] * (len(edges) - 1)
    for v in sample:
        # Left-inclusive, right-inclusive on the final bin.
        for i in range(len(edges) - 1):
            if (v >= edges[i] and v < edges[i + 1]) or (
                i == len(edges) - 2 and v <= edges[i + 1]
            ):
                counts[i] += 1
                break
    total = sum(counts) or 1
    return [c / total for c in counts]


def psi(
    reference: Sequence[float],
    current: Sequence[float],
    bins: int = 10,
) -> float:
    """Population Stability Index between two samples on the same feature.

    Both samples are binned by ``reference``'s quantiles, smoothed by
    ``_EPS`` to avoid ``log(0)``, then summed as ``Σ (c - r) * log(c / r)``.
    """

    if not reference or not current:
        return 0.0
    edges = _quantile_edges(reference, bins)
    ref = _histogram(reference, edges)
    cur = _histogram(current, edges)
    total = 0.0
    for r, c in zip(ref, cur, strict=True):
        r = max(r, _EPS)
        c = max(c, _EPS)
        total += (c - r) * math.log(c / r)
    return total


def psi_report(
    reference: dict[str, Sequence[float]],
    current: dict[str, Sequence[float]],
    bins: int = 10,
) -> dict[str, float]:
    """Per-feature PSI dictionary. Features present in only one side are
    skipped — unknown schema changes are a separate alarm, not drift."""

    shared = set(reference.keys()) & set(current.keys())
    return {f: psi(reference[f], current[f], bins=bins) for f in sorted(shared)}
