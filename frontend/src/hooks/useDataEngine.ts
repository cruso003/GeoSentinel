import { useEffect, useRef } from 'react';
import { useUIStore } from '@/store/uiStore';
import { useAlertStore } from '@/store/alertStore';
import { useSensorStore } from '@/store/sensorStore';
import { startMockEngine, stopMockEngine } from '@/mock/engine';
import { useWebSocket } from './useWebSocket';
import { useLiveHydrate } from './useLiveHydrate';

// Drives the data layer.
// - Mock mode: runs the in-browser simulation via startMockEngine.
// - Live mode: hydrates REST once, then subscribes to the WebSocket hub.
export function useDataEngine(): void {
  const mockMode = useUIStore((s) => s.mockMode);
  const scenario = useUIStore((s) => s.activeScenario);
  const scenarioStart = useUIStore((s) => s.scenarioStartedAt);
  const siteId = useUIStore((s) => s.activeSiteId);
  const prevSite = useRef(siteId);

  useEffect(() => {
    if (!mockMode) return;
    startMockEngine(scenario, scenarioStart);
    return () => stopMockEngine();
  }, [mockMode, scenario, scenarioStart]);

  // Site switch in live mode: prior node readings + alerts are scoped to
  // the old siteId, so wipe them before useLiveHydrate refills.
  useEffect(() => {
    if (prevSite.current !== siteId) {
      if (!mockMode) {
        useAlertStore.getState().clear();
        useSensorStore.getState().reset();
      }
      prevSite.current = siteId;
    }
  }, [siteId, mockMode]);

  useLiveHydrate(siteId, !mockMode);
  useWebSocket(siteId, !mockMode);
}
