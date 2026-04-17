import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { useAlertStore } from '@/store/alertStore';

// Full-screen overlay shown for EVACUATION-tier alerts (Spec 10.1).
// Cannot be dismissed without acknowledging.
export function CriticalAlertOverlay() {
  const evac = useAlertStore((s) => s.evacuationAlertActive);
  const evacAlert = useAlertStore((s) => s.activeAlerts.find((a) => a.severity === 'EVACUATION'));
  const ack = useAlertStore((s) => s.acknowledgeAlert);

  if (!evac || !evacAlert) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-violet-950/85 backdrop-blur-sm">
      <div className="max-w-lg rounded-2xl border-2 border-violet-400 bg-violet-900/95 p-8 text-center shadow-2xl">
        <ShieldAlert className="mx-auto mb-4 h-16 w-16 text-violet-200 animate-pulse-alarm" />
        <h2 className="mb-2 text-2xl font-bold text-white">EVACUATION ALERT</h2>
        <p className="mb-4 text-violet-100">{evacAlert.message}</p>
        <div className="mb-6 flex items-center justify-center gap-2 rounded-lg bg-violet-950/40 p-3 text-sm text-violet-200">
          <AlertTriangle className="h-4 w-4" />
          Follow site evacuation procedure immediately. Do not enter affected zone.
        </div>
        <button
          type="button"
          onClick={() => ack(evacAlert.id, 'operator')}
          className="rounded-md bg-white px-6 py-2 text-sm font-bold text-violet-900 hover:bg-violet-100"
        >
          Acknowledge & Confirm Action Taken
        </button>
      </div>
    </div>
  );
}
