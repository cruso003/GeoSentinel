import { AlertTriangle, ShieldAlert, Info, AlertCircle } from 'lucide-react';
import { useAlertStore } from '@/store/alertStore';
import { fmtAgo } from '@/utils/format';
import { clsx } from '@/utils/clsx';
import type { Alert, AlertSeverity } from '@/types';
import { useState } from 'react';
import { AlertModal } from './AlertModal';

const SEV: Record<AlertSeverity, { color: string; icon: React.ReactNode; ring: string }> = {
  INFO: { color: 'text-blue-300', icon: <Info className="h-4 w-4" />, ring: 'border-l-blue-500' },
  WARNING: {
    color: 'text-amber-300',
    icon: <AlertCircle className="h-4 w-4" />,
    ring: 'border-l-amber-500',
  },
  CRITICAL: {
    color: 'text-red-300',
    icon: <AlertTriangle className="h-4 w-4" />,
    ring: 'border-l-red-500',
  },
  EVACUATION: {
    color: 'text-violet-200',
    icon: <ShieldAlert className="h-4 w-4" />,
    ring: 'border-l-violet-500',
  },
};

export function AlertFeed({
  limit = 50,
  alerts: propAlerts,
}: {
  limit?: number;
  alerts?: Alert[];
}) {
  const storeAlerts = useAlertStore((s) => s.alerts);
  const alerts = propAlerts ?? storeAlerts;
  const [open, setOpen] = useState<Alert | null>(null);

  if (alerts.length === 0) {
    return (
      <div className="gs-card p-4 text-sm text-slate-400">
        No alerts yet. The site is operating within parameters.
      </div>
    );
  }

  return (
    <>
      <ul className="gs-card divide-y divide-bg-line/70 overflow-hidden p-0">
        {alerts.slice(0, limit).map((a) => {
          const sev = SEV[a.severity];
          return (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => setOpen(a)}
                className={clsx(
                  'flex w-full items-start gap-3 border-l-4 px-3 py-2.5 text-left transition hover:bg-bg-line/40',
                  sev.ring,
                  !a.acknowledged && 'animate-pulse-slow',
                )}
              >
                <span className={clsx('mt-0.5', sev.color)}>{sev.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className={clsx('text-[10px] font-bold uppercase', sev.color)}>
                      {a.severity}
                    </span>
                    <span className="text-xs text-slate-400">
                      {a.node_id} · {a.parameter}
                    </span>
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-slate-200">
                    {a.message}
                  </span>
                  <span className="mt-1 block text-[10px] text-slate-500">
                    {fmtAgo(a.created_at)}
                    {a.acknowledged && a.acknowledged_by && ` · ack by ${a.acknowledged_by}`}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {open && <AlertModal alert={open} onClose={() => setOpen(null)} />}
    </>
  );
}
