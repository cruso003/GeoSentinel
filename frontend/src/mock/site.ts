import type { MineSite, MineSlope, SensorNode } from '@/types';

// Tokadeh Pilot Site (Section 6.1) — fictional iron-ore site,
// Nimba County, Liberia. 7.4 N, -8.7 E.

export const TOKADEH_SITE_ID = 'tokadeh-pilot';

export const MOCK_NODES: SensorNode[] = [
  {
    id: 'ENV-01',
    site_id: TOKADEH_SITE_ID,
    node_type: 'ENVIRONMENTAL',
    name: 'ENV-01 Drainage Outflow',
    lat: 7.4012,
    lng: -8.7045,
    elevation_m: 412,
    battery_pct: 87,
    signal_rssi: -68,
    last_seen: new Date().toISOString(),
    status: 'ONLINE',
    calibration_due: '2026-07-10',
  },
  {
    id: 'ENV-02',
    site_id: TOKADEH_SITE_ID,
    node_type: 'ENVIRONMENTAL',
    name: 'ENV-02 Tailings Pond N',
    lat: 7.4089,
    lng: -8.6998,
    elevation_m: 520,
    battery_pct: 74,
    signal_rssi: -71,
    last_seen: new Date().toISOString(),
    status: 'ONLINE',
    calibration_due: '2026-05-02',
  },
  {
    id: 'ENV-03',
    site_id: TOKADEH_SITE_ID,
    node_type: 'ENVIRONMENTAL',
    name: 'ENV-03 Community Intake',
    lat: 7.3921,
    lng: -8.7112,
    elevation_m: 280,
    battery_pct: 92,
    signal_rssi: -78,
    last_seen: new Date().toISOString(),
    status: 'ONLINE',
    calibration_due: '2026-06-22',
  },
  {
    id: 'GEO-01',
    site_id: TOKADEH_SITE_ID,
    node_type: 'GEOTECHNICAL',
    name: 'GEO-01 N Pit Wall A',
    lat: 7.4067,
    lng: -8.7021,
    elevation_m: 605,
    battery_pct: 81,
    signal_rssi: -65,
    last_seen: new Date().toISOString(),
    status: 'ONLINE',
    calibration_due: '2026-08-15',
  },
  {
    id: 'GEO-02',
    site_id: TOKADEH_SITE_ID,
    node_type: 'GEOTECHNICAL',
    name: 'GEO-02 Tailings Dam E',
    lat: 7.4102,
    lng: -8.6971,
    elevation_m: 528,
    battery_pct: 64,
    signal_rssi: -72,
    last_seen: new Date().toISOString(),
    status: 'ONLINE',
    calibration_due: '2026-05-30',
  },
];

export const MOCK_SLOPES: MineSlope[] = [
  {
    id: 'slope-north-a',
    site_id: TOKADEH_SITE_ID,
    name: 'North Wall Sector A',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-8.7035, 7.4055],
          [-8.7005, 7.4058],
          [-8.7000, 7.4078],
          [-8.7032, 7.4080],
          [-8.7035, 7.4055],
        ],
      ],
    },
    mesh_vertices: [
      [-50, 0, -30],
      [-30, 0, -50],
      [-10, 30, -40],
      [-40, 30, -20],
    ],
    current_risk: null,
  },
  {
    id: 'slope-tailings-east',
    site_id: TOKADEH_SITE_ID,
    name: 'Tailings Dam East Face',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-8.6985, 7.4090],
          [-8.6960, 7.4095],
          [-8.6958, 7.4115],
          [-8.6986, 7.4112],
          [-8.6985, 7.4090],
        ],
      ],
    },
    mesh_vertices: [
      [40, 0, 30],
      [60, 0, 20],
      [60, 20, 40],
      [40, 20, 50],
    ],
    current_risk: null,
  },
];

export const MOCK_SITE: MineSite = {
  id: TOKADEH_SITE_ID,
  name: 'Tokadeh Pilot Site',
  region: 'Nimba County',
  country: 'Liberia',
  centroid: { lat: 7.4035, lng: -8.7025 },
  boundary: {
    type: 'Polygon',
    coordinates: [
      [
        [-8.7150, 7.3900],
        [-8.6940, 7.3905],
        [-8.6920, 7.4135],
        [-8.7160, 7.4140],
        [-8.7150, 7.3900],
      ],
    ],
  },
  nodes: MOCK_NODES,
  slopes: MOCK_SLOPES,
};
