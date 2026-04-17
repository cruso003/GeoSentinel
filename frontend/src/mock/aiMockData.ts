import type {
  EnviroGuardPrediction,
  RiskTier,
  Scenario,
  SlopeAlertTier,
  SlopeWatchPrediction,
} from '@/types';
import { TOKADEH_SITE_ID, MOCK_SLOPES } from './site';
import { clamp, lerp, smooth } from './random';
import { scenarioProgress } from './scenarios';

// Per spec Section 6.3 — AI predictions are derived from the
// underlying mock-sensor scenario state, not independent random values.

interface AIOpts {
  scenario: Scenario;
  scenarioStart: number;
}

function tierFromScore(score: number): RiskTier {
  if (score >= 0.8) return 'CRITICAL';
  if (score >= 0.5) return 'HIGH';
  if (score >= 0.25) return 'ELEVATED';
  return 'LOW';
}

function slopeTierFromScore(score: number): SlopeAlertTier {
  if (score >= 0.85) return 'EVACUATION';
  if (score >= 0.7) return 'CRITICAL';
  if (score >= 0.45) return 'WARNING';
  if (score >= 0.25) return 'WATCH';
  return 'NORMAL';
}

export function genEnviroGuard(at: Date, opts: AIOpts): EnviroGuardPrediction {
  const t = at.getTime();
  const frac = scenarioProgress(opts.scenarioStart, opts.scenario, t) ?? 0;

  // Baseline low risk.
  let cond24 = 0.05;
  let cond72 = 0.10;
  let ph24 = 0.04;
  let ph72 = 0.08;
  let turb24 = 0.06;
  let turb72 = 0.12;
  let do24 = 0.04;
  let pm25_24 = 0.07;

  if (opts.scenario === 'tailings_seepage') {
    // Conductivity exceedance probability climbs from 0.05 -> 0.85+ ahead of breach.
    cond24 = lerp(0.05, 0.88, smooth(frac));
    cond72 = clamp(cond24 + 0.07, 0, 0.97);
  }
  if (opts.scenario === 'rainfall_event') {
    ph24 = lerp(0.04, 0.55, smooth(frac));
    turb24 = lerp(0.06, 0.78, smooth(frac));
    do24 = lerp(0.04, 0.4, smooth(frac));
    ph72 = clamp(ph24 + 0.05, 0, 0.95);
    turb72 = clamp(turb24 + 0.05, 0, 0.95);
  }

  const overall24 = Math.max(cond24, ph24, turb24, do24, pm25_24);
  const overall72 = Math.max(cond72, ph72, turb72);

  return {
    site_id: TOKADEH_SITE_ID,
    timestamp: at.toISOString(),
    ph_exceedance_24h: ph24,
    turbidity_exceedance_24h: turb24,
    do_exceedance_24h: do24,
    conductivity_exceedance_24h: cond24,
    pm25_exceedance_24h: pm25_24,
    ph_exceedance_72h: ph72,
    turbidity_exceedance_72h: turb72,
    overall_risk_24h: tierFromScore(overall24),
    overall_risk_72h: tierFromScore(overall72),
    confidence: 0.78 + 0.1 * (1 - frac),
  };
}

export function genSlopeWatch(at: Date, opts: AIOpts): SlopeWatchPrediction[] {
  const t = at.getTime();
  const frac = scenarioProgress(opts.scenarioStart, opts.scenario, t) ?? 0;

  return MOCK_SLOPES.map((slope) => {
    let risk = 0.15;
    let pp = 0.15;
    let tilt = 0.1;
    let insar = 0.08;
    let rain = 0.1;

    if (opts.scenario === 'slope_warning' && slope.id === 'slope-north-a') {
      // Progress from 0.15 -> 0.62 (NORMAL -> WATCH -> WARNING) per spec.
      risk = lerp(0.15, 0.62, smooth(frac));
      pp = lerp(0.2, 0.65, smooth(frac));
      tilt = lerp(0.1, 0.7, smooth(frac));
      insar = lerp(0.08, 0.45, smooth(frac));
      rain = 0.18;
    }
    if (opts.scenario === 'rainfall_event' && slope.id === 'slope-north-a') {
      risk = lerp(0.15, 0.4, smooth(frac));
      pp = lerp(0.2, 0.55, smooth(frac));
      rain = lerp(0.1, 0.7, smooth(frac));
    }

    const trend =
      frac > 0.05 && frac < 0.95
        ? 'DETERIORATING'
        : frac >= 0.95
          ? 'STABLE'
          : 'STABLE';

    return {
      site_id: TOKADEH_SITE_ID,
      slope_id: slope.id,
      timestamp: at.toISOString(),
      risk_score: risk,
      alert_tier: slopeTierFromScore(risk),
      pore_pressure_factor: pp,
      tilt_factor: tilt,
      insar_factor: insar,
      rainfall_factor: rain,
      trend,
      trend_rate: trend === 'DETERIORATING' ? 0.08 : 0,
    } as SlopeWatchPrediction;
  });
}
