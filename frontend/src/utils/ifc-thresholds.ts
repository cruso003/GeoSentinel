// IFC EHS Guideline thresholds (Spec Section 4.2)
// Reference: IFC General EHS Guidelines, Mining Sector Guidelines.
//
// Values here MUST stay aligned with ``backend/app/services/thresholds.py``.
// A backend parity test (``test_thresholds_parity.py``) will fail CI if
// either file is edited without the other.  Pending extraction to a
// shared JSON file (see ``docs/roadmap/functional-gaps.md``).
//
// Unit convention: µg/m³ for SO₂ and NO₂ (WHO / IFC canonical form).
// The frontend previously used ppm for both, which drifted ~87× from
// the backend's µg/m³ check — reconciled here so a single reading
// cannot be "safe" on one side and "exceedance" on the other.
export const IFC_THRESHOLDS = {
  ph: { min: 6.0, max: 9.0, unit: 'SU' },
  turbidity: { max: 5, unit: 'NTU' },
  dissolved_oxygen: { min: 6.0, unit: 'mg/L' },
  conductivity: { max: 500, unit: 'uS/cm' },
  pm25: { max: 25, unit: 'ug/m3' },
  pm10: { max: 50, unit: 'ug/m3' },
  so2: { max: 40, unit: 'ug/m3' },
  no2: { max: 40, unit: 'ug/m3' },
  noise_db: { max: 70, unit: 'dB' },
} as const;

export type IfcParamKey = keyof typeof IFC_THRESHOLDS;

export interface ComplianceCheck {
  compliant: boolean;
  near_limit: boolean;
  exceeded: boolean;
}

// Returns compliance state for a single reading.
// "near_limit" = within 20% of any threshold.
export function checkCompliance(param: IfcParamKey, value: number | null): ComplianceCheck {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return { compliant: true, near_limit: false, exceeded: false };
  }
  const t = IFC_THRESHOLDS[param] as { min?: number; max?: number };
  let exceeded = false;
  let near_limit = false;
  if (t.max !== undefined) {
    if (value > t.max) exceeded = true;
    else if (value > t.max * 0.8) near_limit = true;
  }
  if (t.min !== undefined) {
    if (value < t.min) exceeded = true;
    else if (value < t.min * 1.2) near_limit = true;
  }
  return { compliant: !exceeded, near_limit, exceeded };
}

export const PARAM_LABELS: Record<string, string> = {
  ph: 'pH',
  turbidity: 'Turbidity',
  dissolved_oxygen: 'Dissolved O\u2082',
  conductivity: 'Conductivity',
  temperature: 'Temperature',
  pm25: 'PM2.5',
  pm10: 'PM10',
  so2: 'SO\u2082',
  no2: 'NO\u2082',
  noise_db: 'Noise',
  pore_pressure: 'Pore Pressure',
  tilt_x: 'Tilt X',
  tilt_y: 'Tilt Y',
  crack_displacement: 'Crack Disp.',
  rainfall_mm: 'Rainfall',
};
