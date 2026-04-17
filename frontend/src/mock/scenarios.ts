import type { Scenario } from '@/types';

export interface ScenarioMeta {
  id: Scenario;
  label: string;
  description: string;
  duration_hours: number; // 0 = continuous / indefinite
  affected_nodes: string[];
}

export const SCENARIOS: Record<Scenario, ScenarioMeta> = {
  normal: {
    id: 'normal',
    label: 'Normal Operations',
    description: 'All parameters within IFC limits. System stable.',
    duration_hours: 0,
    affected_nodes: ['ENV-01', 'ENV-02', 'ENV-03', 'GEO-01', 'GEO-02'],
  },
  rainfall_event: {
    id: 'rainfall_event',
    label: 'Wet-Season Rainfall Event',
    description: 'Tropical storm. Turbidity & pH stress. Pore pressure rising.',
    duration_hours: 6,
    affected_nodes: ['ENV-01', 'GEO-01'],
  },
  tailings_seepage: {
    id: 'tailings_seepage',
    label: 'Tailings Pond Seepage',
    description: 'Gradual conductivity rise at ENV-02. EnviroGuard predicts breach 24h ahead.',
    duration_hours: 12,
    affected_nodes: ['ENV-02'],
  },
  slope_warning: {
    id: 'slope_warning',
    label: 'Slope Warning Progression',
    description: 'GEO-01 tilt accelerating. SlopeWatch escalates NORMAL\u2192WATCH\u2192WARNING.',
    duration_hours: 3,
    affected_nodes: ['GEO-01'],
  },
  node_offline: {
    id: 'node_offline',
    label: 'Node Offline',
    description: 'ENV-03 loses comms. Alert fires; other nodes continue normally.',
    duration_hours: 0,
    affected_nodes: ['ENV-03'],
  },
};

// Returns elapsed-time fraction (0..1) of the scenario, or null when continuous.
export function scenarioProgress(start: number, scenario: Scenario, now: number): number | null {
  const meta = SCENARIOS[scenario];
  if (meta.duration_hours === 0) return null;
  const elapsedH = (now - start) / 3_600_000;
  return Math.min(1, Math.max(0, elapsedH / meta.duration_hours));
}
