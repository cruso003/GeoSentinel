import { useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { Gauge } from '@/components/charts/Gauge';
import { TimeSeriesChart, type SeriesPoint } from '@/components/charts/TimeSeriesChart';
import { useSensorStore } from '@/store/sensorStore';
import { useAIStore } from '@/store/aiStore';
import { IFC_THRESHOLDS, PARAM_LABELS, checkCompliance, type IfcParamKey } from '@/utils/ifc-thresholds';
import { fmtNum } from '@/utils/format';
import { clsx } from '@/utils/clsx';
import type { EnvSensorReading } from '@/types';

const WATER_PARAMS: IfcParamKey[] = ['ph', 'turbidity', 'dissolved_oxygen', 'conductivity'];
const AIR_PARAMS: IfcParamKey[] = ['pm25', 'pm10', 'so2', 'no2', 'noise_db'];
const RANGES = ['1h', '6h', '24h', '7d', '30d'] as const;

export function EnvironmentalTab() {
  const [category, setCategory] = useState<'water' | 'air'>('water');
  const [param, setParam] = useState<IfcParamKey>('ph');
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h');
  const env = useSensorStore((s) => s.envHistory);
  const latest = useSensorStore((s) => s.latestEnvReadings);
  const eg = useAIStore((s) => s.enviroguardPrediction);

  const params = category === 'water' ? WATER_PARAMS : AIR_PARAMS;
  const threshold = IFC_THRESHOLDS[param] as { min?: number; max?: number; unit: string };

  const data: SeriesPoint[] = useMemo(() => {
    const stepMap: Record<typeof RANGES[number], number> = {
      '1h': 12,
      '6h': 72,
      '24h': 288,
      '7d': 288 * 7,
      '30d': 288 * 30,
    };
    const lim = stepMap[range];
    const merged: Record<string, SeriesPoint> = {};
    for (const node of ['ENV-01', 'ENV-02', 'ENV-03']) {
      const series = (env[node] ?? []).slice(-lim);
      for (const r of series) {
        if (!merged[r.timestamp]) merged[r.timestamp] = { t: r.timestamp };
        const v = r[param as keyof EnvSensorReading] as number | null;
        merged[r.timestamp][node] = v;
      }
    }
    return Object.values(merged).sort((a, b) => (a.t < b.t ? -1 : 1));
  }, [env, param, range]);

  const eg24 = exceedanceFor(param, eg, '24h');
  const eg72 = exceedanceFor(param, eg, '72h');

  return (
    <div className="space-y-4 p-4">
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1 rounded-md bg-bg-deep p-1">
            {(['water', 'air'] as const).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => {
                  setCategory(c);
                  setParam(c === 'water' ? 'ph' : 'pm25');
                }}
                className={clsx(
                  'rounded px-3 py-1 text-xs font-semibold uppercase tracking-wider',
                  category === c ? 'bg-brand-primary text-white' : 'text-slate-400 hover:text-white',
                )}
              >
                {c === 'water' ? 'Water Quality' : 'Air Quality'}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 overflow-x-auto">
            {params.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setParam(p)}
                className={clsx(
                  'rounded px-3 py-1 text-xs',
                  param === p ? 'bg-bg-line text-white' : 'text-slate-400 hover:text-white',
                )}
              >
                {PARAM_LABELS[p] ?? p}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1 rounded-md bg-bg-deep p-1">
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={clsx(
                  'rounded px-2 py-0.5 text-xs',
                  range === r ? 'bg-brand-primary text-white' : 'text-slate-400 hover:text-white',
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card title={`${PARAM_LABELS[param]} (${threshold.unit})`} subtitle={`History · ${range} · all nodes`}>
        <TimeSeriesChart
          data={data}
          series={['ENV-01', 'ENV-02', 'ENV-03']}
          unit={threshold.unit}
          thresholdMax={threshold.max}
          thresholdMin={threshold.min}
        />
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="EnviroGuard Prediction" subtitle="LSTM + Attention model · 96h input">
          <div className="flex flex-wrap items-center justify-around gap-4">
            <Gauge value={eg24} label={`${PARAM_LABELS[param]} 24h`} sublabel="Exceedance prob." />
            <Gauge value={eg72} label={`${PARAM_LABELS[param]} 72h`} sublabel="Exceedance prob." />
          </div>
          <div className="mt-3 flex items-center justify-center gap-3">
            <Pill tone={tierTone(eg?.overall_risk_24h)}>{eg?.overall_risk_24h ?? '—'} (24h)</Pill>
            <Pill tone={tierTone(eg?.overall_risk_72h)}>{eg?.overall_risk_72h ?? '—'} (72h)</Pill>
            {eg && (
              <span className="text-xs text-slate-400">
                Confidence {(eg.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </Card>

        <Card title="Node Comparison" subtitle="Latest reading · IFC compliance" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Parameter</th>
                  <th className="py-2 pr-3">ENV-01</th>
                  <th className="py-2 pr-3">ENV-02</th>
                  <th className="py-2 pr-3">ENV-03</th>
                  <th className="py-2 pr-3">IFC Limit</th>
                </tr>
              </thead>
              <tbody>
                {params.map((p) => {
                  const t = IFC_THRESHOLDS[p] as { min?: number; max?: number; unit: string };
                  return (
                    <tr key={p} className="border-t border-bg-line">
                      <td className="py-1.5 pr-3 text-slate-300">{PARAM_LABELS[p]}</td>
                      {(['ENV-01', 'ENV-02', 'ENV-03'] as const).map((node) => {
                        const v = latest[node]?.[p as keyof EnvSensorReading] as number | null;
                        const c = checkCompliance(p, v);
                        const cls = c.exceeded
                          ? 'bg-red-500/20 text-red-300'
                          : c.near_limit
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-emerald-500/10 text-emerald-300';
                        return (
                          <td key={node} className={clsx('rounded px-2 py-1.5 font-mono text-xs', cls)}>
                            {fmtNum(v, p === 'ph' ? 2 : 1)}
                          </td>
                        );
                      })}
                      <td className="py-1.5 pr-3 text-xs text-slate-400">
                        {t.min !== undefined && `≥ ${t.min} `}
                        {t.max !== undefined && `≤ ${t.max} `}
                        {t.unit}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

function exceedanceFor(
  param: IfcParamKey,
  eg: ReturnType<typeof useAIStore.getState>['enviroguardPrediction'],
  horizon: '24h' | '72h',
): number {
  if (!eg) return 0;
  const map24: Partial<Record<IfcParamKey, number>> = {
    ph: eg.ph_exceedance_24h,
    turbidity: eg.turbidity_exceedance_24h,
    dissolved_oxygen: eg.do_exceedance_24h,
    conductivity: eg.conductivity_exceedance_24h,
    pm25: eg.pm25_exceedance_24h,
  };
  const map72: Partial<Record<IfcParamKey, number>> = {
    ph: eg.ph_exceedance_72h,
    turbidity: eg.turbidity_exceedance_72h,
  };
  return (horizon === '24h' ? map24[param] : map72[param]) ?? 0;
}

function tierTone(tier: string | undefined): 'good' | 'caution' | 'alert' | 'critical' | 'neutral' {
  if (!tier) return 'neutral';
  if (tier === 'CRITICAL') return 'critical';
  if (tier === 'HIGH') return 'alert';
  if (tier === 'ELEVATED') return 'caution';
  return 'good';
}
