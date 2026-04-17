import { create } from 'zustand';
import type { Alert } from '@/types';

interface AlertState {
  alerts: Alert[];
  activeAlerts: Alert[];
  criticalAlertActive: boolean;
  evacuationAlertActive: boolean;
  addAlert: (alert: Alert) => void;
  acknowledgeAlert: (alertId: string, by: string, notes?: string) => void;
  hydrate: (alerts: Alert[]) => void;
  clear: () => void;
}

const ALERT_CAP = 250;

function recompute(alerts: Alert[]): Pick<AlertState, 'activeAlerts' | 'criticalAlertActive' | 'evacuationAlertActive'> {
  const activeAlerts = alerts.filter((a) => !a.acknowledged);
  return {
    activeAlerts,
    criticalAlertActive: activeAlerts.some((a) => a.severity === 'CRITICAL'),
    evacuationAlertActive: activeAlerts.some((a) => a.severity === 'EVACUATION'),
  };
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  activeAlerts: [],
  criticalAlertActive: false,
  evacuationAlertActive: false,
  addAlert: (alert) =>
    set((s) => {
      // Dedup: same node + parameter + severity within 60s = collapsed.
      const recent = s.alerts.find(
        (a) =>
          !a.acknowledged &&
          a.node_id === alert.node_id &&
          a.parameter === alert.parameter &&
          a.severity === alert.severity &&
          Date.now() - new Date(a.created_at).getTime() < 60_000,
      );
      if (recent) return s;
      const next = [alert, ...s.alerts].slice(0, ALERT_CAP);
      return { alerts: next, ...recompute(next) };
    }),
  acknowledgeAlert: (alertId, by, notes) =>
    set((s) => {
      const next = s.alerts.map((a) =>
        a.id === alertId
          ? {
              ...a,
              acknowledged: true,
              acknowledged_by: by,
              acknowledged_at: new Date().toISOString(),
              message: notes ? `${a.message} \u2014 note: ${notes}` : a.message,
            }
          : a,
      );
      return { alerts: next, ...recompute(next) };
    }),
  hydrate: (alerts) => set({ alerts, ...recompute(alerts) }),
  clear: () => set({ alerts: [], activeAlerts: [], criticalAlertActive: false, evacuationAlertActive: false }),
}));
