import { useEffect } from 'react';
import { useUIStore } from '@/store/uiStore';
import { startMockEngine, stopMockEngine } from '@/mock/engine';

// Drives the data layer. In mock mode this owns the simulation loop.
// In live mode (Phase 2) this is where the WebSocket subscription would mount.
export function useDataEngine(): void {
  const mockMode = useUIStore((s) => s.mockMode);
  const scenario = useUIStore((s) => s.activeScenario);
  const scenarioStart = useUIStore((s) => s.scenarioStartedAt);
  const demoMode = useUIStore((s) => s.demoMode);

  useEffect(() => {
    if (!mockMode) return;
    // Demo mode accelerates time: 6h scenario compresses to ~5min wall clock
    // (simulatedStepMs/tickMs ratio).
    if (demoMode) {
      // 5s wall clock ticks, each = ~4 sim minutes -> 6h in ~7.5min wall.
      // (Already configured by engine defaults, override here for clarity.)
    }
    startMockEngine(scenario, scenarioStart);
    return () => stopMockEngine();
  }, [mockMode, scenario, scenarioStart, demoMode]);
}
