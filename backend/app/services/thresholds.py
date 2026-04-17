"""IFC / WHO compliance thresholds — backend source of truth (Spec §4.2).

Mirrors `frontend/src/utils/ifc-thresholds.ts`. Keep these two files in sync;
if you change one, change the other. The `near_limit` band is 20% of the span
(or 20% below the max for one-sided limits).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Threshold:
    parameter: str
    unit: str
    min_value: Optional[float]
    max_value: Optional[float]
    severity_on_breach: Literal["INFO", "WARNING", "CRITICAL"]


IFC_THRESHOLDS: dict[str, Threshold] = {
    "ph": Threshold("ph", "pH", 6.0, 9.0, "WARNING"),
    "turbidity": Threshold("turbidity", "NTU", None, 5.0, "WARNING"),
    "dissolved_oxygen": Threshold("dissolved_oxygen", "mg/L", 5.0, None, "WARNING"),
    "conductivity": Threshold("conductivity", "uS/cm", None, 500.0, "WARNING"),
    "pm25": Threshold("pm25", "ug/m3", None, 25.0, "WARNING"),
    "pm10": Threshold("pm10", "ug/m3", None, 50.0, "WARNING"),
    "so2": Threshold("so2", "ug/m3", None, 40.0, "INFO"),
    "no2": Threshold("no2", "ug/m3", None, 40.0, "INFO"),
    "noise_db": Threshold("noise_db", "dB", None, 75.0, "INFO"),
    "tilt_x": Threshold("tilt_x", "deg", -0.5, 0.5, "CRITICAL"),
    "tilt_y": Threshold("tilt_y", "deg", -0.5, 0.5, "CRITICAL"),
    "crack_displacement": Threshold("crack_displacement", "mm", None, 3.0, "CRITICAL"),
    "pore_pressure": Threshold("pore_pressure", "kPa", None, 80.0, "WARNING"),
}


@dataclass
class Compliance:
    compliant: bool
    near_limit: bool
    exceeded: bool


def check(parameter: str, value: float) -> Compliance:
    t = IFC_THRESHOLDS.get(parameter)
    if t is None:
        return Compliance(True, False, False)

    exceeded = False
    near = False

    if t.min_value is not None and value < t.min_value:
        exceeded = True
    if t.max_value is not None and value > t.max_value:
        exceeded = True

    if not exceeded:
        if t.min_value is not None and t.max_value is not None:
            span = (t.max_value - t.min_value) * 0.2
            if value < t.min_value + span or value > t.max_value - span:
                near = True
        elif t.max_value is not None and value > t.max_value * 0.8:
            near = True
        elif t.min_value is not None and value < t.min_value * 1.2:
            near = True

    return Compliance(compliant=not exceeded, near_limit=near, exceeded=exceeded)
