import type { Scenario } from '@/types';
import { MOCK_NODES } from './site';
import { genEnvHistory, genEnvReadings } from './envMockData';
import { genGeoHistory, genGeoReadings } from './geoMockData';
import { genEnviroGuard, genSlopeWatch } from './aiMockData';
import {
  deriveEnvAlerts,
  deriveEnviroGuardAlerts,
  deriveSlopeAlerts,
  geoThresholdAlerts,
  offlineNodeAlert,
} from './alertsMockData';
import { useSensorStore } from '@/store/sensorStore';
import { useAlertStore } from '@/store/alertStore';
import { useAIStore } from '@/store/aiStore';

interface EngineConfig {
  scenario: Scenario;
  scenarioStart: number;
  tickMs: number;          // wall-clock ms between ticks
  simulatedStepMs: number; // simulated time per tick (for accelerated demos)
}

const DEFAULT_CONFIG: EngineConfig = {
  scenario: 'normal',
  scenarioStart: Date.now(),
  tickMs: 5_000,
  simulatedStepMs: 60_000,
};

let timer: ReturnType<typeof setInterval> | null = null;
let cfg: EngineConfig = { ...DEFAULT_CONFIG };
let cursor = Date.now();
let aiCounter = 0;
let offlineFired = false;

export function configureEngine(partial: Partial<EngineConfig>): void {
  cfg = { ...cfg, ...partial };
}

export function bootstrapHistory(scenario: Scenario, scenarioStart: number): void {
  const now = new Date();
  const env = useSensorStore.getState();
  const ai = useAIStore.getState();
  const opts = { scenario, scenarioStart };

  for (const node of MOCK_NODES) {
    if (node.node_type === 'ENVIRONMENTAL') {
      const hist = genEnvHistory(node.id, now, 24 * 12, 5 * 60_000, opts); // 24h @ 5min
      env.hydrateEnvHistory(node.id, hist);
      env.setLatestEnvReading(hist[hist.length - 1]);
    } else {
      const hist = genGeoHistory(node.id, now, 24 * 12, 5 * 60_000, opts);
      env.hydrateGeoHistory(node.id, hist);
      env.setLatestGeoReading(hist[hist.length - 1]);
    }
  }

  // Seed one AI prediction so panels aren't blank.
  ai.setEnviroguardPrediction(genEnviroGuard(now, opts));
  for (const p of genSlopeWatch(now, opts)) ai.setSlopeWatchPrediction(p);
}

export function startMockEngine(scenario: Scenario, scenarioStart: number): void {
  stopMockEngine();
  configureEngine({ scenario, scenarioStart });
  cursor = Date.now();
  offlineFired = false;
  bootstrapHistory(scenario, scenarioStart);

  timer = setInterval(tick, cfg.tickMs);
}

export function stopMockEngine(): void {
  if (timer) clearInterval(timer);
  timer = null;
}

function tick(): void {
  cursor += cfg.simulatedStepMs;
  const at = new Date(cursor);
  const opts = { scenario: cfg.scenario, scenarioStart: cfg.scenarioStart };

  const sensor = useSensorStore.getState();
  const alert = useAlertStore.getState();
  const ai = useAIStore.getState();

  const envReadings = genEnvReadings(at, opts);
  for (const r of envReadings) {
    if (cfg.scenario === 'node_offline' && r.node_id === 'ENV-03') {
      if (!offlineFired) {
        alert.addAlert(offlineNodeAlert('ENV-03'));
        offlineFired = true;
      }
      continue;
    }
    sensor.setLatestEnvReading(r);
    sensor.appendEnvHistory(r.node_id, r);
    for (const a of deriveEnvAlerts(r)) alert.addAlert(a);
  }

  const geoReadings = genGeoReadings(at, opts);
  for (const r of geoReadings) {
    sensor.setLatestGeoReading(r);
    sensor.appendGeoHistory(r.node_id, r);
    for (const a of geoThresholdAlerts(r)) alert.addAlert(a);
  }

  // Run AI inference every ~3 ticks (i.e. every 15min sim time at default cadence).
  if (++aiCounter % 3 === 0) {
    const eg = genEnviroGuard(at, opts);
    ai.setEnviroguardPrediction(eg);
    for (const a of deriveEnviroGuardAlerts(eg)) alert.addAlert(a);

    for (const sw of genSlopeWatch(at, opts)) {
      ai.setSlopeWatchPrediction(sw);
      for (const a of deriveSlopeAlerts(sw)) alert.addAlert(a);
    }
  }
}
