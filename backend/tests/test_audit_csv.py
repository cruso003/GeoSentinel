"""CSV formula-injection guard (Phase 2.1 §2)."""

import pytest

from app.services.csv_safe import csv_safe


@pytest.mark.parametrize("bad", ["=1+1", "+cmd", "-2", "@SUM(A1)", "\tfoo", "\rbar"])
def test_csv_safe_prefixes_formula_leader(bad):
    out = csv_safe(bad)
    assert out.startswith("'")
    assert out[1:] == bad


@pytest.mark.parametrize("ok", ["alice@example.com", "login", "site-01", "normal text"])
def test_csv_safe_passes_through_normal_text(ok):
    assert csv_safe(ok) == ok


def test_csv_safe_handles_none():
    assert csv_safe(None) == ""


def test_csv_safe_handles_non_string():
    assert csv_safe(123) == "123"
