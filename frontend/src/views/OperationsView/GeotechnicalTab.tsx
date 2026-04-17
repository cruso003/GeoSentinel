import { useMemo, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { useAIStore } from '@/store/aiStore';
import { useSensorStore } from '@/store/sensorStore';
import { MOCK_SLOPES } from '@/mock/site';
import { format, parseISO } from 'date-fns';
import { clsx } from '@/utils/clsx';

const RANGES = ['24h', '7d', '30d'] as const;

const TIER_TONE = {
  NORMAL: 'good',
  WATCH: 'info',
  WARNING: 'caution',
  CRITICAL: 'critical',
  EVACUATION: 'evacuation',
} as const;

export function GeotechnicalTab() {
  const slopes = useAIStore((s) => s.slopeWatchPredictions);
  const geoHist = useSensorStore((s) => s.geoHistory);

  const sorted = useMemo(
    () =>
      [...MOCK_SLOPES].sort(
        (a, b) => (slopes[b.id]?.risk_score ?? 0) - (slopes[a.id]?.risk_score ?? 0),
      ),
    [slopes],
  );
  const [slopeId, setSlopeId] = useState(sorted[0]?.id ?? MOCK_SLOPES[0].id);
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h');

  const slope = MOCK_SLOPES.find((s) => s.id === slopeId)!;
  const pred = slopes[slopeId];
  const tier = pred?.alert_tier ?? 'NORMAL';

  const stepMap: Record<typeof RANGES[number], number> = {
    '24h': 288,
    '7d': 288 * 7,
    '30d': 288 * 30,
  };
  const lim = stepMap[range];
  const geoNode = slopeId === 'slope-north-a' ? 'GEO-01' : 'GEO-02';
  const tiltData = (geoHist[geoNode] ?? []).slice(-lim).map((r) => ({
    t: r.timestamp,
    'tilt_x (°)': r.tilt_x,
    'tilt_y (°)': r.tilt_y,
  }));
  const ppData = (geoHist[geoNode] ?? []).slice(-lim).map((r) => ({
    t: r.timestamp,
    pore_pressure: r.pore_pressure,
    rainfall: r.rainfall_mm,
  }));

  const TrendIcon = pred?.trend === 'DETERIORATING' ? ArrowUpRight : pred?.trend === 'IMPROVING' ? ArrowDownRight : Minus;

  return (
    <div className="space-y-4 p-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs text-slate-400">Slope segment</label>
          <select
            value={slopeId}
            onChange={(e) => setSlopeId(e.target.value)}
            className="gs-input max-w-xs text-xs"
          >
            {sorted.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {Math.round((slopes[s.id]?.risk_score ?? 0) * 100)}%
              </option>
            ))}
          </select>
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title={slope.name} subtitle="SlopeWatch (PINN) risk score">
          <div className="flex flex-col items-center justify-center py-2">
            <RiskRing score={pred?.risk_score ?? 0} />
            <Pill tone={TIER_TONE[tier]} className="mt-3">
              {tier}
            </Pill>
            <div className="mt-2 flex items-center gap-1 text-xs text-slate-400">
              <TrendIcon className="h-4 w-4" />
              {pred?.trend ?? 'STABLE'} ({pred?.trend_rate ?? 0}/h)
            </div>
          </div>
        </Card>
        <Card title="Factor Breakdown" subtitle="Why this risk score?" className="lg:col-span-2">
          <div className="space-y-2">
            <FactorBar label="Pore Water Pressure" value={pred?.pore_pressure_factor ?? 0} />
            <FactorBar label="Tilt Accumulation" value={pred?.tilt_factor ?? 0} />
            <FactorBar label="InSAR Displacement" value={pred?.insar_factor ?? 0} />
            <FactorBar label="Rainfall Intensity" value={pred?.rainfall_factor ?? 0} />
          </div>
          <p className="mt-3 text-[11px] text-slate-500">
            Physics constraint: Mohr-Coulomb factor of safety informs final risk score. FS &lt; 1.0
            forces risk &gt; 0.9.
          </p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={`${geoNode} · Tilt (°)`} subtitle="X / Y axes vs baseline">
          <TimeSeriesChart
            data={tiltData}
            series={['tilt_x (°)', 'tilt_y (°)']}
            unit="°"
            thresholdMax={0.4}
          />
        </Card>
        <Card title={`${geoNode} · Pore Pressure & Rainfall`} subtitle="Coupled hydrology">
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={ppData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1F3A5F" strokeDasharray="3 3" />
              <XAxis
                dataKey="t"
                stroke="#64748B"
                fontSize={11}
                tickFormatter={(v) => format(parseISO(v as string), 'HH:mm')}
                minTickGap={32}
              />
              <YAxis yAxisId="left" stroke="#64748B" fontSize={11} width={48} />
              <YAxis yAxisId="right" orientation="right" stroke="#64748B" fontSize={11} width={48} />
              <Tooltip
                contentStyle={{
                  background: '#0F1F36',
                  border: '1px solid #1F3A5F',
                  borderRadius: 8,
                  color: '#F1F5F9',
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94A3B8' }} />
              <Bar yAxisId="right" dataKey="rainfall" name="Rainfall (mm/hr)" fill="#3B82F6" opacity={0.4} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="pore_pressure"
                name="Pore P. (bar)"
                stroke="#22D3EE"
                strokeWidth={1.6}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}

function RiskRing({ score }: { score: number }) {
  const v = Math.max(0, Math.min(1, score));
  const r = 60;
  const c = 2 * Math.PI * r;
  const color = v >= 0.7 ? '#EF4444' : v >= 0.45 ? '#F59E0B' : v >= 0.25 ? '#FACC15' : '#10B981';
  return (
    <svg width={160} height={160} viewBox="0 0 160 160">
      <circle cx={80} cy={80} r={r} stroke="#1F3A5F" strokeWidth={12} fill="none" />
      <circle
        cx={80}
        cy={80}
        r={r}
        stroke={color}
        strokeWidth={12}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={`${c * v} ${c}`}
        transform="rotate(-90 80 80)"
      />
      <text x={80} y={86} textAnchor="middle" fontSize="28" fontWeight="700" fill="#F1F5F9">
        {Math.round(v * 100)}%
      </text>
    </svg>
  );
}

function FactorBar({ label, value }: { label: string; value: number }) {
  const v = Math.max(0, Math.min(1, value));
  const color = v >= 0.7 ? 'bg-red-500' : v >= 0.4 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-300">{label}</span>
        <span className="font-mono text-slate-400">{Math.round(v * 100)}%</span>
      </div>
      <div className="mt-1 h-2 w-full rounded-full bg-bg-line">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${v * 100}%` }} />
      </div>
    </div>
  );
}
