// GeoSentinel core type definitions (Spec Section 4)

// ---------------------------------------------------------------------------
// 4.1.1 Sensor data
// ---------------------------------------------------------------------------

export interface EnvSensorReading {
  node_id: string;
  site_id: string;
  timestamp: string; // ISO 8601
  ph: number | null; // 0-14
  turbidity: number | null; // NTU
  dissolved_oxygen: number | null; // mg/L
  conductivity: number | null; // uS/cm
  temperature: number | null; // Celsius
  pm25: number | null; // ug/m3
  pm10: number | null; // ug/m3
  so2: number | null; // ppm
  no2: number | null; // ppm
  noise_db: number | null; // dB SPL
}

export interface GeoSensorReading {
  node_id: string;
  site_id: string;
  timestamp: string;
  tilt_x: number | null; // degrees from baseline
  tilt_y: number | null;
  crack_displacement: number | null; // mm cumulative
  pore_pressure: number | null; // bar
  seismic_event: boolean;
  seismic_magnitude: number | null;
  rainfall_mm: number | null; // mm/hr
}

export type SensorReading = EnvSensorReading | GeoSensorReading;

// ---------------------------------------------------------------------------
// 4.1.2 AI model outputs
// ---------------------------------------------------------------------------

export type RiskTier = 'LOW' | 'ELEVATED' | 'HIGH' | 'CRITICAL';

export interface EnviroGuardPrediction {
  site_id: string;
  timestamp: string;
  ph_exceedance_24h: number;
  turbidity_exceedance_24h: number;
  do_exceedance_24h: number;
  conductivity_exceedance_24h: number;
  pm25_exceedance_24h: number;
  ph_exceedance_72h: number;
  turbidity_exceedance_72h: number;
  overall_risk_24h: RiskTier;
  overall_risk_72h: RiskTier;
  confidence: number; // 0.0 - 1.0
}

export type SlopeAlertTier = 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL' | 'EVACUATION';
export type SlopeTrend = 'STABLE' | 'DETERIORATING' | 'IMPROVING';

export interface SlopeWatchPrediction {
  site_id: string;
  slope_id: string;
  timestamp: string;
  risk_score: number; // 0.0 - 1.0
  alert_tier: SlopeAlertTier;
  pore_pressure_factor: number;
  tilt_factor: number;
  insar_factor: number;
  rainfall_factor: number;
  trend: SlopeTrend;
  trend_rate: number; // change per hour
}

// ---------------------------------------------------------------------------
// 4.1.3 Alerts
// ---------------------------------------------------------------------------

export type AlertType =
  | 'ENV_THRESHOLD'
  | 'ENV_PREDICTED'
  | 'GEO_THRESHOLD'
  | 'GEO_PREDICTED'
  | 'NODE_OFFLINE'
  | 'CALIBRATION_DUE';

export type AlertSeverity = 'INFO' | 'WARNING' | 'CRITICAL' | 'EVACUATION';

export interface Alert {
  id: string;
  site_id: string;
  node_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  parameter: string;
  value: number | null;
  threshold: number | null;
  message: string;
  created_at: string;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

// ---------------------------------------------------------------------------
// 4.1.4 Site & node
// ---------------------------------------------------------------------------

export type NodeType = 'ENVIRONMENTAL' | 'GEOTECHNICAL';
export type NodeStatus = 'ONLINE' | 'OFFLINE' | 'DEGRADED';

export interface SensorNode {
  id: string;
  site_id: string;
  node_type: NodeType;
  name: string;
  lat: number;
  lng: number;
  elevation_m: number;
  battery_pct: number; // 0-100
  signal_rssi: number; // dBm
  last_seen: string;
  status: NodeStatus;
  calibration_due: string; // ISO date
}

export interface MineSlope {
  id: string;
  site_id: string;
  name: string;
  geometry: GeoJSON.Polygon;
  mesh_vertices: [number, number, number][];
  current_risk: SlopeWatchPrediction | null;
}

export interface MineSite {
  id: string;
  name: string;
  region: string;
  country: string;
  centroid: { lat: number; lng: number };
  boundary: GeoJSON.Polygon;
  nodes: SensorNode[];
  slopes: MineSlope[];
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type UserRole = 'operator' | 'esg_admin' | 'community';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  user: User;
}

// ---------------------------------------------------------------------------
// WebSocket message envelope (Section 5.3)
// ---------------------------------------------------------------------------

export type WSMessage =
  | { type: 'SENSOR_UPDATE'; data: EnvSensorReading | GeoSensorReading }
  | { type: 'ALERT_NEW'; data: Alert }
  | { type: 'ALERT_ACKNOWLEDGED'; data: { alert_id: string } }
  | { type: 'AI_PREDICTION'; data: EnviroGuardPrediction | SlopeWatchPrediction }
  | { type: 'NODE_STATUS'; data: { node_id: string; status: NodeStatus } };

// ---------------------------------------------------------------------------
// Mock-mode scenarios (Section 6.2)
// ---------------------------------------------------------------------------

export type Scenario =
  | 'normal'
  | 'rainfall_event'
  | 'tailings_seepage'
  | 'slope_warning'
  | 'node_offline';

// ---------------------------------------------------------------------------
// Community view simplified status (Section 9)
// ---------------------------------------------------------------------------

export type PlainStatus = 'GOOD' | 'CAUTION' | 'ALERT' | 'CRITICAL';

export interface CommunityStatus {
  site_id: string;
  overall: PlainStatus;
  water: { status: PlainStatus; explanation: string; updated_at: string };
  air: { status: PlainStatus; explanation: string; updated_at: string };
  ground: { status: PlainStatus; explanation: string; updated_at: string };
}

// ---------------------------------------------------------------------------
// ESG report meta
// ---------------------------------------------------------------------------

export type ReportType = 'IFC_PERFORMANCE' | 'ISO_14001' | 'CUSTOM_SUMMARY';
export type ReportStatus = 'pending' | 'generating' | 'ready' | 'failed';

export interface ComplianceReport {
  id: string;
  site_id: string;
  report_type: ReportType;
  period_start: string;
  period_end: string;
  status: ReportStatus;
  download_url: string | null;
  generated_at: string | null;
  data_integrity_hash: string | null;
  // Phase 3 §IFC PDF offline signing — base64 Ed25519 signature + 64-char
  // hex pubkey. Null for legacy pre-signing reports or when signing failed
  // in a non-production environment.
  signature_b64: string | null;
  signing_pubkey_hex: string | null;
}
