import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { Sparkline } from './Sparkline';
import { clsx } from '@/utils/clsx';

export type KpiTrend = 'up' | 'down' | 'flat';

export function KpiCard({
  label,
  value,
  unit,
  trend,
  spark,
  tone = 'neutral',
  hint,
}: {
  label: string;
  value: string;
  unit?: string;
  trend?: KpiTrend;
  spark?: { v: number | null }[];
  tone?: 'good' | 'caution' | 'alert' | 'neutral';
  hint?: string;
}) {
  const TrendIcon = trend === 'up' ? ArrowUp : trend === 'down' ? ArrowDown : Minus;
  const toneClass =
    tone === 'good'
      ? 'text-emerald-300'
      : tone === 'caution'
        ? 'text-amber-300'
        : tone === 'alert'
          ? 'text-red-300'
          : 'text-slate-100';
  const strokeColor =
    tone === 'alert' ? '#EF4444' : tone === 'caution' ? '#F59E0B' : tone === 'good' ? '#10B981' : '#22D3EE';

  return (
    <div className="gs-card p-3">
      <div className="flex items-baseline justify-between">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {label}
        </div>
        {trend && (
          <span className={clsx('flex items-center gap-0.5 text-[10px]', toneClass)}>
            <TrendIcon className="h-3 w-3" />
          </span>
        )}
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <div className={clsx('text-2xl font-bold tabular-nums', toneClass)}>{value}</div>
        {unit && <div className="text-xs text-slate-500">{unit}</div>}
      </div>
      {hint && <div className="text-[10px] text-slate-500">{hint}</div>}
      {spark && spark.length > 1 && (
        <div className="mt-2">
          <Sparkline data={spark} color={strokeColor} />
        </div>
      )}
    </div>
  );
}
