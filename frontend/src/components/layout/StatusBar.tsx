import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { Pill } from '@/components/ui/Pill';
import { useAIStore } from '@/store/aiStore';
import { useAlertStore } from '@/store/alertStore';
import { useSensorStore } from '@/store/sensorStore';
import { fmtAgo } from '@/utils/format';

export function StatusBar() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const eg = useAIStore((s) => s.enviroguardPrediction);
  const slopes = useAIStore((s) => s.slopeWatchPredictions);
  const activeAlerts = useAlertStore((s) => s.activeAlerts);
  const env = useSensorStore((s) => s.latestEnvReadings);

  const envRisk = eg?.overall_risk_24h ?? 'LOW';
  const envTone =
    envRisk === 'CRITICAL'
      ? 'critical'
      : envRisk === 'HIGH'
        ? 'alert'
        : envRisk === 'ELEVATED'
          ? 'caution'
          : 'good';

  const slopeTier = Object.values(slopes).reduce<string>((acc, s) => {
    const order = ['NORMAL', 'WATCH', 'WARNING', 'CRITICAL', 'EVACUATION'];
    return order.indexOf(s.alert_tier) > order.indexOf(acc) ? s.alert_tier : acc;
  }, 'NORMAL');
  const slopeTone =
    slopeTier === 'EVACUATION'
      ? 'evacuation'
      : slopeTier === 'CRITICAL'
        ? 'critical'
        : slopeTier === 'WARNING'
          ? 'alert'
          : slopeTier === 'WATCH'
            ? 'caution'
            : 'good';

  const lastReading = Object.values(env).reduce<string | null>((acc, r) => {
    if (!acc) return r.timestamp;
    return r.timestamp > acc ? r.timestamp : acc;
  }, null);

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-bg-line bg-bg-panel/70 px-4 py-3 text-xs text-slate-300">
      <div className="flex items-center gap-3">
        <Clock className="h-4 w-4 text-slate-500" />
        <span className="font-mono">{now.toUTCString().slice(5, 25)} UTC</span>
        <span className="text-slate-600">·</span>
        <span>Tokadeh, Liberia (UTC+0)</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-slate-500">Environmental</span>
        <Pill tone={envTone}>{envRisk}</Pill>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">Geohazard</span>
        <Pill tone={slopeTone}>{slopeTier}</Pill>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">Alerts</span>
        <Pill tone={activeAlerts.length > 0 ? 'alert' : 'neutral'}>{activeAlerts.length}</Pill>
        {lastReading && (
          <span className="text-slate-500">last data {fmtAgo(lastReading)}</span>
        )}
      </div>
    </header>
  );
}
