import type { Scenario } from '@/types';

export interface WalkthroughStep {
  id: string;
  title: string;
  body: string;
  route: string;
  scenario?: Scenario;
  durationMs: number;
}

// 3-4 minute narrated tour (Spec §16).
export const WALKTHROUGH_STEPS: WalkthroughStep[] = [
  {
    id: 'intro-overview',
    title: 'Welcome to GeoSentinel',
    body:
      'You are watching the Tokadeh iron-ore mine in Nimba County, Liberia. ' +
      'Five IoT nodes stream water, air and slope data in real time.',
    route: '/operations/overview',
    scenario: 'normal',
    durationMs: 18000,
  },
  {
    id: 'rainfall',
    title: 'A rainfall event arrives',
    body:
      'Watch turbidity climb at the downstream node and pore pressure rise on ' +
      'the north slope. Operators see the correlation in one place.',
    route: '/operations/environmental',
    scenario: 'rainfall_event',
    durationMs: 30000,
  },
  {
    id: 'enviroguard',
    title: 'EnviroGuard looks 24 h ahead',
    body:
      'The LSTM+Attention model flags a rising probability of a pH exceedance ' +
      '— giving the operator a 24 h lead time before the IFC limit is crossed.',
    route: '/operations/environmental',
    scenario: 'rainfall_event',
    durationMs: 22000,
  },
  {
    id: 'tailings',
    title: 'A tailings seepage event',
    body:
      'Conductivity drifts at ENV-02 and pH ticks alkaline. EnviroGuard\'s ' +
      'conductivity 24 h probability jumps, raising a predictive alert.',
    route: '/operations/environmental',
    scenario: 'tailings_seepage',
    durationMs: 25000,
  },
  {
    id: 'slope',
    title: 'SlopeWatch escalates WATCH → WARNING',
    body:
      'Tilt on GEO-01 grows; the PINN combines tilt, pore pressure, InSAR ' +
      'and rainfall into a single risk score. The digital twin highlights ' +
      'the affected bench with an exclusion cylinder.',
    route: '/operations/geotechnical',
    scenario: 'slope_warning',
    durationMs: 30000,
  },
  {
    id: 'twin',
    title: '3D digital twin',
    body:
      'Orbit the pit, toggle slope risk, exclusion zones, and sensor markers. ' +
      'Everything updates with the same live data feed the 2D views use.',
    route: '/operations/twin',
    scenario: 'slope_warning',
    durationMs: 22000,
  },
  {
    id: 'alerts',
    title: 'Acknowledge the alert',
    body:
      'Operators acknowledge predictive and threshold alerts. Every action is ' +
      'written to the immutable audit log for regulators.',
    route: '/operations/alerts',
    scenario: 'slope_warning',
    durationMs: 20000,
  },
  {
    id: 'esg',
    title: 'Generate an ESG report',
    body:
      'The ESG admin generates an IFC-aligned PDF with SHA-256 data integrity ' +
      'in under 30 seconds — ready for the government and IFC.',
    route: '/esg',
    scenario: 'normal',
    durationMs: 24000,
  },
  {
    id: 'community',
    title: 'Community transparency',
    body:
      'Residents near the mine get a plain-language dashboard: drinking water, ' +
      'air, and ground stability — always public, always current.',
    route: '/community/tokadeh-liberia',
    scenario: 'normal',
    durationMs: 20000,
  },
];

export const WALKTHROUGH_TOTAL_MS = WALKTHROUGH_STEPS.reduce(
  (acc, s) => acc + s.durationMs,
  0,
);
