"""Subscription-backed recipient resolver + SMS template rendering."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from app.services.notifications import SEVERITY_RANK, validate_e164
from app.services.notifications_templates import AVAILABLE_LANGUAGES, render


def test_severity_rank_monotonic():
    assert SEVERITY_RANK["INFO"] < SEVERITY_RANK["WARNING"]
    assert SEVERITY_RANK["WARNING"] < SEVERITY_RANK["CRITICAL"]
    assert SEVERITY_RANK["CRITICAL"] < SEVERITY_RANK["EVACUATION"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+231881234567", "+231881234567"),
        (" +14155552671 ", "+14155552671"),
        ("231881234567", None),  # missing +
        ("+not-digits", None),
        ("+123", None),  # too short
        ("+" + "1" * 16, None),  # too long
        (None, None),
        ("", None),
    ],
)
def test_validate_e164(raw, expected):
    assert validate_e164(raw) == expected


def test_templates_cover_every_language():
    # Core keys must exist in English; every other language falls back to en
    # if it doesn't define a given key.
    keys = {"slope_evacuation", "water_quality_critical", "air_quality_critical", "test"}
    for lang in AVAILABLE_LANGUAGES:
        for key in keys:
            out = render(language=lang, key=key, site="Tokadeh")
            assert "Tokadeh" in out or lang != "en", (lang, key, out)
            assert out  # never empty


def test_template_fallback_when_key_unknown():
    out = render(
        language="mano", key="definitely-not-a-real-key", site="Tokadeh",
        severity="CRITICAL", message="demo"
    )
    assert "Tokadeh" in out
    assert "CRITICAL" in out


def test_template_fallback_when_language_unknown():
    # Unknown language → English baseline. ``test`` interpolates ``site``.
    out = render(language="klingon", key="test", site="Tokadeh")
    assert "Tokadeh" in out
    assert "test" in out.lower()
