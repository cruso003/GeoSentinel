import type { MineSite, MineSlope, SensorNode } from '@/types';

// Tokadeh / Yekepa reference site — real Mount Nimba range coordinates
// (summit ~7.608 N, 8.422 W; ArcelorMittal Liberia town of Yekepa
// ~7.577 N, 8.544 W).  Elevations match the Copernicus GLO-30 DEM tile
// shipped at /dem/nimba.json so the twin, map, and node positions all
// agree on the same geography.

export const TOKADEH_SITE_ID = 'tokadeh-pilot';

export const MOCK_NODES: SensorNode[] = [
  {
    id: 'ENV-01',
    site_id: TOKADEH_SITE_ID,
    node_type: 'ENVIRONMENTAL',
    name: 'ENV-01 Drainage Outflow',
    lat: 7.5700,
    lng: -8.5440,
    elevation_m: 560,
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
    lat: 7.5825,
    lng: -8.5305,
    elevation_m: 620,
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
    lat: 7.5610,
    lng: -8.5570,
    elevation_m: 480,
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
    lat: 7.5970,
    lng: -8.4600,
    elevation_m: 1420,
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
    lat: 7.5880,
    lng: -8.5265,
    elevation_m: 640,
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
          [-8.4650, 7.5950],
          [-8.4550, 7.5955],
          [-8.4540, 7.5995],
          [-8.4645, 7.6000],
          [-8.4650, 7.5950],
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
          [-8.5295, 7.5860],
          [-8.5240, 7.5870],
          [-8.5235, 7.5905],
          [-8.5290, 7.5900],
          [-8.5295, 7.5860],
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
  name: 'Tokadeh / Yekepa Reference Site',
  region: 'Nimba County',
  country: 'Liberia',
  centroid: { lat: 7.5775, lng: -8.5000 },
  boundary: {
    type: 'Polygon',
    coordinates: [
      [
        [-8.5700, 7.5500],
        [-8.4500, 7.5500],
        [-8.4500, 7.6050],
        [-8.5700, 7.6050],
        [-8.5700, 7.5500],
      ],
    ],
  },
  nodes: MOCK_NODES,
  slopes: MOCK_SLOPES,
};
