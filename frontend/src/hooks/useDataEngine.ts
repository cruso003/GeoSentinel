import { useEffect } from 'react';
import { useUIStore } from '@/store/uiStore';
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

  useEffect(() => {
    if (!mockMode) return;
    startMockEngine(scenario, scenarioStart);
    return () => stopMockEngine();
  }, [mockMode, scenario, scenarioStart]);

  useLiveHydrate(siteId, !mockMode);
  useWebSocket(siteId, !mockMode);
}
