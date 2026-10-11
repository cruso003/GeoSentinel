"""Guard against frontend/backend IFC threshold drift (Spec §4.2).

The backend's ``services.thresholds.IFC_THRESHOLDS`` and the frontend's
``frontend/src/utils/ifc-thresholds.ts`` are two independent sources of
truth that CLAUDE.md explicitly promises will stay aligned. The brutal
review found they had drifted — units differed (SO2/NO2 in ppm on the
frontend vs µg/m³ on the backend, 87× in SO2's case), one-sided limits
were different numbers (noise 70 vs 75 dB), and nobody caught it because
nothing checked.

This test parses the TS literal with a small regex and asserts the
backend has the same min/max for every parameter the frontend declares.
It fails if either file changes without the other, which is enough CI
pressure to keep the files synchronised until the shared JSON extraction
in ``docs/roadmap/functional-gaps.md`` lands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.thresholds import IFC_THRESHOLDS

_FRONTEND_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "ifc-thresholds.ts"
)

# Matches a line like:  pm25: { max: 25, unit: 'ug/m3' },
# or:                   ph: { min: 6.0, max: 9.0, unit: 'SU' },
_ROW_RE = re.compile(
    r"^\s*(\w+):\s*\{\s*(?P<body>[^}]*)\}\s*,?\s*$",
    re.MULTILINE,
)
_FIELD_RE = re.compile(r"(min|max)\s*:\s*(-?\d+(?:\.\d+)?)")


def _parse_frontend_thresholds() -> dict[str, dict[str, float]]:
    text = _FRONTEND_PATH.read_text()
    start = text.index("export const IFC_THRESHOLDS")
    end = text.index("} as const", start)
    block = text[start:end]
    parsed: dict[str, dict[str, float]] = {}
    for m in _ROW_RE.finditer(block):
        name = m.group(1)
        if name == "export":
            continue
        body = m.group("body")
        fields = {k: float(v) for k, v in _FIELD_RE.findall(body)}
        if fields:
            parsed[name] = fields
    return parsed


@pytest.fixture(scope="module")
def frontend_thresholds() -> dict[str, dict[str, float]]:
    assert _FRONTEND_PATH.exists(), f"Frontend thresholds file missing at {_FRONTEND_PATH}"
    parsed = _parse_frontend_thresholds()
    assert parsed, "Frontend parser returned nothing — regex likely out of date"
    return parsed


def test_every_frontend_param_has_a_backend_match(frontend_thresholds):
    missing = [name for name in frontend_thresholds if name not in IFC_THRESHOLDS]
    assert not missing, (
        f"Frontend declares thresholds the backend has not mirrored: {missing}. "
        f"Add them to backend/app/services/thresholds.py."
    )


def test_shared_params_have_matching_bounds(frontend_thresholds):
    mismatches: list[str] = []
    for name, fe in frontend_thresholds.items():
        be = IFC_THRESHOLDS[name]
        fe_min = fe.get("min")
        fe_max = fe.get("max")
        if fe_min is not None and be.min_value != fe_min:
            mismatches.append(
                f"{name}.min: frontend={fe_min} backend={be.min_value}"
            )
        if fe_max is not None and be.max_value != fe_max:
            mismatches.append(
                f"{name}.max: frontend={fe_max} backend={be.max_value}"
            )
        if fe_min is None and be.min_value is not None:
            mismatches.append(
                f"{name}.min: frontend absent backend={be.min_value}"
            )
        if fe_max is None and be.max_value is not None:
            mismatches.append(
                f"{name}.max: frontend absent backend={be.max_value}"
            )
    assert not mismatches, (
        "Frontend / backend IFC thresholds have drifted:\n  - "
        + "\n  - ".join(mismatches)
    )
