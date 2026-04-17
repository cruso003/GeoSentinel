import { useEffect } from 'react';
import { api, ApiError } from '@/api/client';
import { useAlertStore } from '@/store/alertStore';
import { useAIStore } from '@/store/aiStore';
import type {
  Alert,
  EnviroGuardPrediction,
  SlopeWatchPrediction,
} from '@/types';

// One-shot REST hydration for live mode. Seeds the alert + AI stores so the
// dashboard isn't empty until the first WebSocket frame arrives.
export function useLiveHydrate(siteId: string, enabled: boolean): void {
  useEffect(() => {
    if (!enabled || !siteId) return;
    let cancelled = false;

    (async () => {
      try {
        const alerts = await api.get<Alert[]>(`/alerts?site_id=${siteId}&limit=100`);
        if (!cancelled) useAlertStore.getState().hydrate(alerts);
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) {
          // Non-auth errors: keep stores empty; WS will fill them.
        }
      }
      try {
        const eg = await api.get<EnviroGuardPrediction | null>(
          `/ai/enviroguard/predictions/${siteId}`,
        );
        if (!cancelled && eg) useAIStore.getState().setEnviroguardPrediction(eg);
      } catch {
        /* ignore */
      }
      try {
        const sw = await api.get<SlopeWatchPrediction[]>(
          `/ai/slopewatch/predictions/${siteId}`,
        );
        if (!cancelled) sw.forEach((p) => useAIStore.getState().setSlopeWatchPrediction(p));
      } catch {
        /* ignore */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [siteId, enabled]);
}
