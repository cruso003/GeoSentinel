"""Mohr-Coulomb factor-of-safety via Bishop's simplified method (Spec §13.2).

Used as a physics-constrained loss term for the SlopeWatch PINN. In Phase 1
the backend serves deterministic risk scores; Phase 2 plugs this into the
training loop so the model's predictions remain consistent with limit-
equilibrium slope stability for the Tokadeh geometry.

Bishop's simplified (circular failure):

    FoS = Σ [ (c' · b + (W - u · b) · tan φ') / m_α ] / Σ (W · sin α)

where m_α = cos α + (sin α · tan φ') / FoS, solved iteratively.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Slice:
    weight: float          # W [kN/m]
    base_angle_deg: float  # α [deg]
    base_length: float     # b [m]
    pore_pressure: float   # u [kPa]


@dataclass
class Soil:
    cohesion: float         # c' [kPa]
    friction_angle_deg: float  # φ' [deg]


def factor_of_safety(
    slices: Iterable[Slice],
    soil: Soil,
    max_iter: int = 50,
    tol: float = 1e-4,
) -> float:
    """Iteratively solve Bishop's simplified FoS for a circular slip surface."""
    slices = list(slices)
    if not slices:
        return float("inf")

    phi = math.radians(soil.friction_angle_deg)
    tan_phi = math.tan(phi)
    denom = sum(s.weight * math.sin(math.radians(s.base_angle_deg)) for s in slices)
    if denom <= 0:
        return float("inf")

    fos = 1.5  # initial guess
    for _ in range(max_iter):
        num = 0.0
        for s in slices:
            alpha = math.radians(s.base_angle_deg)
            m_alpha = math.cos(alpha) + (math.sin(alpha) * tan_phi) / fos
            if m_alpha <= 0:
                return float("nan")  # slice failure — method invalid
            shear = soil.cohesion * s.base_length + max(s.weight - s.pore_pressure * s.base_length, 0.0) * tan_phi
            num += shear / m_alpha
        new_fos = num / denom
        if abs(new_fos - fos) < tol:
            return new_fos
        fos = new_fos
    return fos


def risk_from_fos(fos: float) -> float:
    """Map FoS → [0,1] risk score. FoS<1.0 → failure; FoS>1.5 → safe."""
    if math.isnan(fos) or fos <= 1.0:
        return 1.0
    if fos >= 1.5:
        return 0.0
    # Linear ramp between 1.0 (FoS=1.0) and 0.0 (FoS=1.5).
    return max(0.0, min(1.0, (1.5 - fos) / 0.5))


def demo_slices() -> List[Slice]:
    """A tiny 6-slice demo surface for the north slope at Tokadeh."""
    return [
        Slice(weight=180, base_angle_deg=55, base_length=3.0, pore_pressure=12),
        Slice(weight=260, base_angle_deg=42, base_length=3.5, pore_pressure=18),
        Slice(weight=310, base_angle_deg=28, base_length=4.0, pore_pressure=22),
        Slice(weight=290, base_angle_deg=14, base_length=4.0, pore_pressure=24),
        Slice(weight=240, base_angle_deg=-2, base_length=4.0, pore_pressure=22),
        Slice(weight=170, base_angle_deg=-16, base_length=3.5, pore_pressure=16),
    ]
