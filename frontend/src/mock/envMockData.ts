import type { EnvSensorReading, Scenario } from '@/types';
import { TOKADEH_SITE_ID } from './site';
import { clamp, diurnalFactor, isWetSeason, lerp, noiseFor, smooth } from './random';
import { scenarioProgress } from './scenarios';

export interface MockEnvOptions {
  scenario: Scenario;
  scenarioStart: number; // ms epoch when scenario activated
}

const ENV_NODE_IDS = ['ENV-01', 'ENV-02', 'ENV-03'] as const;
type EnvNodeId = (typeof ENV_NODE_IDS)[number];

// Generate one reading per env node at the given timestamp.
export function genEnvReadings(at: Date, opts: MockEnvOptions): EnvSensorReading[] {
  return ENV_NODE_IDS.map((id) => genEnvReading(id, at, opts));
}

export function genEnvReading(
  nodeId: EnvNodeId | string,
  at: Date,
  opts: MockEnvOptions,
): EnvSensorReading {
  const t = at.getTime();
  const wet = isWetSeason(at);
  const diur = diurnalFactor(at);
  const noise = (s: number) => noiseFor(nodeId, t, s);

  // Scenario fraction (0..1) over scenario duration.
  const frac = scenarioProgress(opts.scenarioStart, opts.scenario, t) ?? 0;

  // Baselines, then scenario perturbations.
  let ph = 7.6 + 0.25 * noise(1);
  let turbidity = (wet ? 5 : 2) + 1.2 * noise(2);
  let dissolved_oxygen = 8 + 0.7 * noise(3);
  let conductivity = 200 + 40 * noise(4);
  const temperature = 28 + 4 * (diur - 0.5) + 0.5 * noise(5);
  let pm25 = 8 + 18 * diur + 4 * noise(6);
  const pm10 = pm25 * 1.6 + 5 * noise(7);
  const so2 = 0.05 + 0.05 * diur + 0.02 * noise(8);
  const no2 = 0.04 + 0.04 * diur + 0.02 * noise(9);
  const noise_db = 52 + 12 * diur + 3 * noise(10);

  // ----- Scenario overlays -----
  if (opts.scenario === 'rainfall_event' && nodeId === 'ENV-01') {
    // Storm: pH dips, turbidity spikes for 2-4hr then recovers.
    const dip = smooth(frac * 2) - smooth((frac - 0.5) * 2);
    ph -= 1.2 * dip; // 7.6 -> 6.4
    turbidity += 30 * dip; // 5 -> 35 NTU peak
    dissolved_oxygen -= 2 * dip;
  }

  if (opts.scenario === 'tailings_seepage' && nodeId === 'ENV-02') {
    // Conductivity rises gradually over 6-12hr from 200 to 460.
    conductivity = lerp(220, 470, smooth(frac));
    // pH drift slightly alkaline (ore leachate).
    ph = lerp(7.6, 8.4, smooth(frac));
  }

  if (opts.scenario === 'node_offline' && nodeId === 'ENV-03') {
    // Returns NaN reading (caller will mark node offline).
    return offlineReading(nodeId, at);
  }

  return {
    node_id: nodeId,
    site_id: TOKADEH_SITE_ID,
    timestamp: at.toISOString(),
    ph: clamp(ph, 6.0, 9.5),
    turbidity: clamp(turbidity, 0.1, 80),
    dissolved_oxygen: clamp(dissolved_oxygen, 3, 12),
    conductivity: clamp(conductivity, 80, 700),
    temperature: clamp(temperature, 18, 38),
    pm25: clamp(pm25, 1, 120),
    pm10: clamp(pm10, 2, 200),
    so2: clamp(so2, 0, 0.6),
    no2: clamp(no2, 0, 0.4),
    noise_db: clamp(noise_db, 35, 90),
  };
}

function offlineReading(nodeId: string, at: Date): EnvSensorReading {
  return {
    node_id: nodeId,
    site_id: TOKADEH_SITE_ID,
    timestamp: at.toISOString(),
    ph: null,
    turbidity: null,
    dissolved_oxygen: null,
    conductivity: null,
    temperature: null,
    pm25: null,
    pm10: null,
    so2: null,
    no2: null,
    noise_db: null,
  };
}

// History generator — N samples ending at `endAt`, spaced by `stepMs`.
export function genEnvHistory(
  nodeId: string,
  endAt: Date,
  count: number,
  stepMs: number,
  opts: MockEnvOptions,
): EnvSensorReading[] {
  const out: EnvSensorReading[] = [];
  for (let i = count - 1; i >= 0; i--) {
    const at = new Date(endAt.getTime() - i * stepMs);
    out.push(genEnvReading(nodeId, at, opts));
  }
  return out;
}
