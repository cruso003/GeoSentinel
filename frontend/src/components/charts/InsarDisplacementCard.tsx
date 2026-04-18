import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { getSlopeInsar, type InsarSeries } from '@/api/sites';
import { clsx } from '@/utils/clsx';

interface Props {
  siteId: string;
  slopeId: string;
}

// Velocity thresholds for the badge, matching velocity_to_factor ladder
// in backend/app/services/insar_ingest.py so frontend + backend agree on
// which numbers are "elevated" vs "critical".
function velocityTone(v: number | null): 'good' | 'caution' | 'critical' {
  if (v === null) return 'good';
  const mag = Math.abs(v);
  if (mag >= 20) return 'critical';
  if (mag >= 5) return 'caution';
  return 'good';
}

export function InsarDisplacementCard({ siteId, slopeId }: Props) {
  const [series, setSeries] = useState<InsarSeries | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getSlopeInsar(siteId, slopeId, 90)
      .then((s) => {
        if (!cancelled) setSeries(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'InSAR fetch failed.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [siteId, slopeId]);

  const velocity = series?.velocity_mm_yr ?? null;
  const tone = velocityTone(velocity);
  const points = series?.points ?? [];
  const chartData = points.map((p) => ({ t: p.timestamp, mm: p.displacement_mm }));

  return (
    <Card
      title="InSAR Displacement"
      subtitle="Cumulative line-of-sight motion, 90-day window"
      actions={
        velocity !== null ? (
          <Pill tone={tone} className="text-xs">
            {velocity > 0 ? '+' : ''}
            {velocity.toFixed(1)} mm/yr
          </Pill>
        ) : null
      }
    >
      {loading && <div className="text-xs text-slate-500">Loading series…</div>}
      {error && (
        <div className="text-xs text-red-400" role="alert">
          {error}
        </div>
      )}
      {!loading && !error && points.length === 0 && (
        <div className="text-xs text-slate-500">
          No Sentinel-1 scenes ingested for this slope yet. The weekly InSAR task runs Sundays 03:00 UTC.
        </div>
      )}
      {!loading && !error && points.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#1F3A5F" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              stroke="#64748B"
              fontSize={11}
              tickFormatter={(v) => format(parseISO(v as string), 'MMM d')}
              minTickGap={32}
            />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              width={48}
              tickFormatter={(v) => `${v} mm`}
            />
            <Tooltip
              contentStyle={{
                background: '#0F1F36',
                border: '1px solid #1F3A5F',
                borderRadius: 8,
                color: '#F1F5F9',
                fontSize: 12,
              }}
              labelFormatter={(v) => format(parseISO(v as string), 'yyyy-MM-dd')}
              formatter={(v: number) => [`${v.toFixed(2)} mm`, 'Displacement']}
            />
            <ReferenceLine y={0} stroke="#64748B" strokeDasharray="2 2" />
            <Line
              type="monotone"
              dataKey="mm"
              stroke={tone === 'critical' ? '#EF4444' : tone === 'caution' ? '#F59E0B' : '#22D3EE'}
              strokeWidth={1.8}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p className={clsx('mt-2 text-[11px]', loading ? 'invisible' : 'text-slate-500')}>
        Sign convention: negative = subsidence (away from satellite); positive = uplift.
      </p>
    </Card>
  );
}
