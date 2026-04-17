import type { GeoSensorReading, Scenario } from '@/types';
import { TOKADEH_SITE_ID } from './site';
import { clamp, isWetSeason, lerp, noiseFor, smooth } from './random';
import { scenarioProgress } from './scenarios';

export interface MockGeoOptions {
  scenario: Scenario;
  scenarioStart: number;
}

const GEO_NODE_IDS = ['GEO-01', 'GEO-02'] as const;
type GeoNodeId = (typeof GEO_NODE_IDS)[number];

export function genGeoReadings(at: Date, opts: MockGeoOptions): GeoSensorReading[] {
  return GEO_NODE_IDS.map((id) => genGeoReading(id, at, opts));
}

export function genGeoReading(
  nodeId: GeoNodeId | string,
  at: Date,
  opts: MockGeoOptions,
): GeoSensorReading {
  const t = at.getTime();
  const wet = isWetSeason(at);
  const noise = (s: number) => noiseFor(nodeId, t, s);

  const frac = scenarioProgress(opts.scenarioStart, opts.scenario, t) ?? 0;

  // Baselines.
  let tilt_x = 0.05 * noise(1);
  let tilt_y = 0.05 * noise(2);
  let crack_displacement = 1.2 + 0.05 * noise(3);
  let pore_pressure = (wet ? 0.55 : 0.32) + 0.04 * noise(4);
  let rainfall_mm = 0;
  let seismic_event = false;
  let seismic_magnitude: number | null = null;

  // Ambient micro-seismic, very rare.
  if (Math.abs(noise(7)) > 0.95) {
    seismic_event = true;
    seismic_magnitude = 0.8 + 0.4 * Math.abs(noise(8));
  }

  // ----- Scenario overlays -----
  if (opts.scenario === 'rainfall_event' && nodeId === 'GEO-01') {
    // Storm peaks then tapers.
    const peak = smooth(frac * 2) - smooth((frac - 0.5) * 2);
    rainfall_mm = 18 * peak; // mm/hr
    pore_pressure += 0.45 * smooth(frac); // 0.55 -> ~1.0 bar
  }

  if (opts.scenario === 'slope_warning' && nodeId === 'GEO-01') {
    // Tilt accelerates over 3hr from baseline to 0.6° on x.
    tilt_x = lerp(0.05, 0.62, smooth(frac));
    tilt_y = lerp(0.04, 0.18, smooth(frac));
    crack_displacement = lerp(1.2, 4.8, smooth(frac));
    pore_pressure = lerp(0.32, 0.85, smooth(frac));
  }

  return {
    node_id: nodeId,
    site_id: TOKADEH_SITE_ID,
    timestamp: at.toISOString(),
    tilt_x: clamp(tilt_x, -1, 1),
    tilt_y: clamp(tilt_y, -1, 1),
    crack_displacement: clamp(crack_displacement, 0, 50),
    pore_pressure: clamp(pore_pressure, 0, 2.5),
    seismic_event,
    seismic_magnitude,
    rainfall_mm: clamp(rainfall_mm, 0, 50),
  };
}

export function genGeoHistory(
  nodeId: string,
  endAt: Date,
  count: number,
  stepMs: number,
  opts: MockGeoOptions,
): GeoSensorReading[] {
  const out: GeoSensorReading[] = [];
  for (let i = count - 1; i >= 0; i--) {
    const at = new Date(endAt.getTime() - i * stepMs);
    out.push(genGeoReading(nodeId, at, opts));
  }
  return out;
}
