import { useState } from 'react';
import { X } from 'lucide-react';
import { useAlertStore } from '@/store/alertStore';
import { useAuthStore } from '@/store/authStore';
import { Pill } from '@/components/ui/Pill';
import { fmtDateTime } from '@/utils/format';
import type { Alert, AlertSeverity } from '@/types';

const TONE: Record<AlertSeverity, 'info' | 'caution' | 'critical' | 'evacuation'> = {
  INFO: 'info',
  WARNING: 'caution',
  CRITICAL: 'critical',
  EVACUATION: 'evacuation',
};

const ROOT_CAUSE: Record<string, string> = {
  conductivity:
    'Sustained conductivity rise consistent with tailings-pond seepage. Recommended action: inspect liner, increase sampling cadence.',
  ph: 'Acid drainage signal during rainfall event. Recommended action: dose lime at outflow weir.',
  turbidity:
    'Sediment plume during storm runoff. Recommended action: deploy temporary settling barrier downstream.',
  slope_risk:
    'Pore-pressure-driven instability detected. Recommended action: clear personnel from affected sector, brief geotechnical lead.',
  connectivity:
    'Node has not reported within heartbeat window. Recommended action: dispatch field crew to inspect node power and antenna.',
  tilt: 'Tilt baseline exceeded. Recommended action: cross-reference with InSAR product and pore pressure trend.',
};

export function AlertModal({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const ack = useAlertStore((s) => s.acknowledgeAlert);
  const session = useAuthStore((s) => s.session);
  const [notes, setNotes] = useState('');
  const canAck = session?.user.role === 'operator' || session?.user.role === 'esg_admin';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="gs-card w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <Pill tone={TONE[alert.severity]}>{alert.severity}</Pill>
            <h3 className="mt-2 text-base font-semibold text-white">
              {alert.node_id} · {alert.parameter}
            </h3>
            <p className="text-xs text-slate-400">
              Alert ID {alert.id} · {fmtDateTime(alert.created_at)}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-bg-line hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </header>

        <p className="mb-3 text-sm text-slate-200">{alert.message}</p>
        {alert.value !== null && alert.threshold !== null && (
          <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-md border border-bg-line bg-bg-deep p-2">
              <div className="text-slate-400">Current value</div>
              <div className="text-base font-semibold text-white">{alert.value}</div>
            </div>
            <div className="rounded-md border border-bg-line bg-bg-deep p-2">
              <div className="text-slate-400">Threshold</div>
              <div className="text-base font-semibold text-white">{alert.threshold}</div>
            </div>
          </div>
        )}

        <div className="mb-4 rounded-md border border-bg-line bg-bg-deep p-3 text-xs text-slate-300">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
            AI Root-Cause Summary
          </div>
          {ROOT_CAUSE[alert.parameter] ?? 'Investigate sensor reading and surrounding context.'}
        </div>

        {!alert.acknowledged && canAck && (
          <div className="space-y-2">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Acknowledgement notes (optional)"
              className="gs-input min-h-[80px] resize-y text-xs"
            />
            <div className="flex justify-end gap-2">
              <button type="button" className="gs-button" onClick={onClose}>
                Close
              </button>
              <button
                type="button"
                className="gs-button-primary"
                onClick={() => {
                  ack(alert.id, session?.user.name ?? 'operator', notes || undefined);
                  onClose();
                }}
              >
                Acknowledge
              </button>
            </div>
          </div>
        )}
        {alert.acknowledged && (
          <div className="text-xs text-slate-400">
            Acknowledged by <span className="text-slate-200">{alert.acknowledged_by}</span>
            {alert.acknowledged_at && ` at ${fmtDateTime(alert.acknowledged_at)}`}
          </div>
        )}
      </div>
    </div>
  );
}
