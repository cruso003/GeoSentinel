"""Training-label schema tests (Phase 2.4 §1).

The router itself talks to the DB + audit service through a pile of async
dependencies we can't spin up without a live SQLAlchemy session. We cover
the schema contract here (the CSV importer reuses it row-by-row, so
validation coverage is the main guard against bad bulk data).
"""

from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from app.schemas.training_labels import TrainingLabelIn


def test_accepts_valid_row():
    row = TrainingLabelIn(
        site_id="tokadeh",
        node_id="ENV-02",
        parameter="conductivity",
        t_start="2026-04-17T00:00:00Z",
        t_end="2026-04-17T01:00:00Z",
        label="exceedance",
        source="field",
    )
    assert row.source == "field"
    assert row.notes is None


def test_rejects_unknown_source():
    with pytest.raises(Exception):
        TrainingLabelIn(
            site_id="tokadeh",
            node_id="ENV-02",
            parameter="conductivity",
            t_start="2026-04-17T00:00:00Z",
            t_end="2026-04-17T01:00:00Z",
            label="exceedance",
            source="hearsay",  # not in LABEL_SOURCES
        )


def test_rejects_inverted_window():
    with pytest.raises(Exception):
        TrainingLabelIn(
            site_id="tokadeh",
            node_id="ENV-02",
            parameter="ph",
            t_start="2026-04-17T02:00:00Z",
            t_end="2026-04-17T01:00:00Z",
            label="exceedance",
            source="field",
        )


def test_rejects_zero_length_window():
    with pytest.raises(Exception):
        TrainingLabelIn(
            site_id="tokadeh",
            node_id="ENV-02",
            parameter="ph",
            t_start="2026-04-17T01:00:00Z",
            t_end="2026-04-17T01:00:00Z",
            label="exceedance",
            source="field",
        )
