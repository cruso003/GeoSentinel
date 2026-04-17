import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Scenario } from '@/types';
import { TOKADEH_SITE_ID } from '@/mock/site';

export type OperationsTab =
  | 'overview'
  | 'environmental'
  | 'geotechnical'
  | 'twin'
  | 'alerts'
  | 'nodes';

export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

interface UIState {
  activeSiteId: string;
  activeView: OperationsTab;
  activeParameter: string;
  timeRange: TimeRange;
  mockMode: boolean;
  activeScenario: Scenario;
  scenarioStartedAt: number;
  demoMode: boolean;
  walkthroughActive: boolean;
  esgLightTheme: boolean;
  setActiveSiteId: (id: string) => void;
  setActiveView: (v: OperationsTab) => void;
  setActiveParameter: (p: string) => void;
  setTimeRange: (r: TimeRange) => void;
  setMockMode: (enabled: boolean) => void;
  setActiveScenario: (s: Scenario) => void;
  setDemoMode: (enabled: boolean) => void;
  setWalkthroughActive: (active: boolean) => void;
  toggleEsgTheme: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      activeSiteId: TOKADEH_SITE_ID,
      activeView: 'overview',
      activeParameter: 'ph',
      timeRange: '24h',
      mockMode: true,
      activeScenario: 'normal',
      scenarioStartedAt: Date.now(),
      demoMode: false,
      walkthroughActive: false,
      esgLightTheme: false,
      setActiveSiteId: (id) => set({ activeSiteId: id }),
      setActiveView: (v) => set({ activeView: v }),
      setActiveParameter: (p) => set({ activeParameter: p }),
      setTimeRange: (r) => set({ timeRange: r }),
      setMockMode: (enabled) => set({ mockMode: enabled }),
      setActiveScenario: (s) => set({ activeScenario: s, scenarioStartedAt: Date.now() }),
      setDemoMode: (enabled) => set({ demoMode: enabled }),
      setWalkthroughActive: (active) => set({ walkthroughActive: active }),
      toggleEsgTheme: () => set((s) => ({ esgLightTheme: !s.esgLightTheme })),
    }),
    {
      name: 'gs.ui',
      partialize: (s) => ({
        activeSiteId: s.activeSiteId,
        activeView: s.activeView,
        activeParameter: s.activeParameter,
        timeRange: s.timeRange,
        mockMode: s.mockMode,
        esgLightTheme: s.esgLightTheme,
      }),
    },
  ),
);
