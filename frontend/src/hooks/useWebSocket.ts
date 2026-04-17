import { useEffect, useRef } from 'react';
import { useSensorStore } from '@/store/sensorStore';
import { useAlertStore } from '@/store/alertStore';
import { useAIStore } from '@/store/aiStore';
import type {
  Alert,
  EnvSensorReading,
  EnviroGuardPrediction,
  GeoSensorReading,
  SlopeWatchPrediction,
} from '@/types';

const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? '';

function wsURL(siteId: string): string {
  if (WS_BASE) return `${WS_BASE.replace(/\/$/, '')}/ws/${siteId}`;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/${siteId}`;
}

// Opens `/ws/{siteId}` when enabled (live mode). Routes server messages into
// the Zustand stores and auto-reconnects with exponential backoff up to 30s.
export function useWebSocket(siteId: string, enabled: boolean): void {
  const retryRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || !siteId) return;
    let disposed = false;

    const appendEnv = useSensorStore.getState().appendEnvHistory;
    const appendGeo = useSensorStore.getState().appendGeoHistory;
    const setLatestEnv = useSensorStore.getState().setLatestEnvReading;
    const setLatestGeo = useSensorStore.getState().setLatestGeoReading;
    const addAlert = useAlertStore.getState().addAlert;
    const ackAlert = useAlertStore.getState().acknowledgeAlert;
    const setEnviroguard = useAIStore.getState().setEnviroguardPrediction;
    const setSlopeWatch = useAIStore.getState().setSlopeWatchPrediction;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(wsURL(siteId));
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
      };

      ws.onmessage = (ev) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        switch (msg.type) {
          case 'SENSOR_UPDATE': {
            const kind = msg.kind as 'env' | 'geo';
            const payload = msg.payload as EnvSensorReading | GeoSensorReading;
            if (kind === 'env') {
              setLatestEnv(payload as EnvSensorReading);
              appendEnv(payload.node_id, payload as EnvSensorReading);
            } else {
              setLatestGeo(payload as GeoSensorReading);
              appendGeo(payload.node_id, payload as GeoSensorReading);
            }
            break;
          }
          case 'ALERT_NEW': {
            addAlert(msg.alert as Alert);
            break;
          }
          case 'ALERT_ACKNOWLEDGED': {
            const alertId = msg.alert_id as string;
            const by = (msg.by as string | undefined) ?? 'system';
            if (alertId) ackAlert(alertId, by);
            break;
          }
          case 'AI_PREDICTION': {
            const model = msg.model as 'enviroguard' | 'slopewatch';
            if (model === 'enviroguard') {
              setEnviroguard(msg.payload as EnviroGuardPrediction);
            } else {
              setSlopeWatch(msg.payload as SlopeWatchPrediction);
            }
            break;
          }
          default:
            break;
        }
      };

      ws.onclose = () => {
        if (disposed) return;
        const delay = Math.min(30_000, 1000 * 2 ** retryRef.current);
        retryRef.current += 1;
        timerRef.current = window.setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      disposed = true;
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
      retryRef.current = 0;
    };
  }, [siteId, enabled]);
}
