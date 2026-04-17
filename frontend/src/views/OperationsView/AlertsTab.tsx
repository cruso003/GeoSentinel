import { useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { AlertFeed } from '@/components/alerts/AlertFeed';
import { useAlertStore } from '@/store/alertStore';
import type { AlertSeverity } from '@/types';
import { clsx } from '@/utils/clsx';

const SEVS: (AlertSeverity | 'ALL')[] = ['ALL', 'INFO', 'WARNING', 'CRITICAL', 'EVACUATION'];

export function AlertsTab() {
  const all = useAlertStore((s) => s.alerts);
  const [sev, setSev] = useState<(typeof SEVS)[number]>('ALL');
  const [showAck, setShowAck] = useState(true);

  const filtered = useMemo(
    () =>
      all.filter((a) => {
        if (sev !== 'ALL' && a.severity !== sev) return false;
        if (!showAck && a.acknowledged) return false;
        return true;
      }),
    [all, sev, showAck],
  );

  return (
    <div className="space-y-4 p-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs uppercase tracking-wider text-slate-500">Severity</span>
          <div className="flex items-center gap-1 rounded-md bg-bg-deep p-1">
            {SEVS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSev(s)}
                className={clsx(
                  'rounded px-2 py-1 text-xs',
                  sev === s ? 'bg-brand-primary text-white' : 'text-slate-400 hover:text-white',
                )}
              >
                {s}
              </button>
            ))}
          </div>
          <label className="ml-auto flex items-center gap-2 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={showAck}
              onChange={(e) => setShowAck(e.target.checked)}
            />
            Show acknowledged
          </label>
        </div>
      </Card>

      {filtered.length === 0 ? (
        <div className="gs-card p-4 text-sm text-slate-400">No matching alerts.</div>
      ) : (
        <AlertFeed limit={filtered.length} alerts={filtered} />
      )}
    </div>
  );
}
