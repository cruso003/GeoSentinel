import type { Alert, EnviroGuardPrediction, EnvSensorReading, GeoSensorReading, Scenario, SlopeWatchPrediction } from '@/types';
import { IFC_THRESHOLDS, checkCompliance, type IfcParamKey } from '@/utils/ifc-thresholds';
import { TOKADEH_SITE_ID } from './site';

let _seq = 0;
const id = () => `alt-${Date.now()}-${++_seq}`;

const ENV_PARAMS: IfcParamKey[] = ['ph', 'turbidity', 'dissolved_oxygen', 'conductivity', 'pm25'];

export function deriveEnvAlerts(reading: EnvSensorReading): Alert[] {
  const out: Alert[] = [];
  for (const p of ENV_PARAMS) {
    const v = (reading as unknown as Record<string, number | null>)[p];
    if (v === null || v === undefined) continue;
    const c = checkCompliance(p, v);
    if (!c.exceeded) continue;
    const t = IFC_THRESHOLDS[p] as { min?: number; max?: number };
    const threshold = t.max ?? t.min ?? null;
    out.push({
      id: id(),
      site_id: reading.site_id,
      node_id: reading.node_id,
      alert_type: 'ENV_THRESHOLD',
      severity: 'WARNING',
      parameter: p,
      value: v,
      threshold,
      message: `${p} reading ${v.toFixed(2)} breaches IFC limit (${threshold ?? '-'})`,
      created_at: reading.timestamp,
      acknowledged: false,
      acknowledged_by: null,
      acknowledged_at: null,
    });
  }
  return out;
}

export function deriveEnviroGuardAlerts(p: EnviroGuardPrediction): Alert[] {
  const out: Alert[] = [];
  const flag: { key: string; prob: number; label: string }[] = [
    { key: 'conductivity_exceedance_24h', prob: p.conductivity_exceedance_24h, label: 'conductivity' },
    { key: 'turbidity_exceedance_24h', prob: p.turbidity_exceedance_24h, label: 'turbidity' },
    { key: 'ph_exceedance_24h', prob: p.ph_exceedance_24h, label: 'ph' },
  ];
  for (const f of flag) {
    if (f.prob >= 0.6) {
      out.push({
        id: id(),
        site_id: p.site_id,
        node_id: 'site',
        alert_type: 'ENV_PREDICTED',
        severity: f.prob >= 0.85 ? 'CRITICAL' : 'WARNING',
        parameter: f.label,
        value: Number(f.prob.toFixed(2)),
        threshold: 0.6,
        message: `EnviroGuard predicts ${f.label} exceedance probability ${(f.prob * 100).toFixed(0)}% within 24h`,
        created_at: p.timestamp,
        acknowledged: false,
        acknowledged_by: null,
        acknowledged_at: null,
      });
    }
  }
  return out;
}

export function deriveSlopeAlerts(p: SlopeWatchPrediction): Alert[] {
  if (p.alert_tier === 'NORMAL') return [];
  const sevMap = {
    WATCH: 'INFO',
    WARNING: 'WARNING',
    CRITICAL: 'CRITICAL',
    EVACUATION: 'EVACUATION',
  } as const;
  return [
    {
      id: id(),
      site_id: p.site_id,
      node_id: p.slope_id,
      alert_type: 'GEO_PREDICTED',
      severity: sevMap[p.alert_tier as keyof typeof sevMap],
      parameter: 'slope_risk',
      value: Number(p.risk_score.toFixed(2)),
      threshold: 0.45,
      message: `SlopeWatch tier ${p.alert_tier} on ${p.slope_id} (risk ${(p.risk_score * 100).toFixed(0)}%)`,
      created_at: p.timestamp,
      acknowledged: false,
      acknowledged_by: null,
      acknowledged_at: null,
    },
  ];
}

export function offlineNodeAlert(nodeId: string): Alert {
  return {
    id: id(),
    site_id: TOKADEH_SITE_ID,
    node_id: nodeId,
    alert_type: 'NODE_OFFLINE',
    severity: 'WARNING',
    parameter: 'connectivity',
    value: null,
    threshold: null,
    message: `${nodeId} has not reported for 5+ minutes`,
    created_at: new Date().toISOString(),
    acknowledged: false,
    acknowledged_by: null,
    acknowledged_at: null,
  };
}

export function geoThresholdAlerts(reading: GeoSensorReading): Alert[] {
  const out: Alert[] = [];
  if ((reading.tilt_x ?? 0) > 0.4 || (reading.tilt_y ?? 0) > 0.4) {
    out.push({
      id: id(),
      site_id: reading.site_id,
      node_id: reading.node_id,
      alert_type: 'GEO_THRESHOLD',
      severity: 'WARNING',
      parameter: 'tilt',
      value: Math.max(reading.tilt_x ?? 0, reading.tilt_y ?? 0),
      threshold: 0.4,
      message: `${reading.node_id} tilt exceeds 0.4° baseline`,
      created_at: reading.timestamp,
      acknowledged: false,
      acknowledged_by: null,
      acknowledged_at: null,
    });
  }
  return out;
}
