import { create } from 'zustand';
import type { EnviroGuardPrediction, SlopeWatchPrediction } from '@/types';

interface AIState {
  enviroguardPrediction: EnviroGuardPrediction | null;
  enviroguardHistory: EnviroGuardPrediction[];
  slopeWatchPredictions: Record<string, SlopeWatchPrediction>;
  slopeWatchHistory: Record<string, SlopeWatchPrediction[]>;
  setEnviroguardPrediction: (p: EnviroGuardPrediction) => void;
  setSlopeWatchPrediction: (p: SlopeWatchPrediction) => void;
  reset: () => void;
}

const AI_HISTORY_CAP = 720;

export const useAIStore = create<AIState>((set) => ({
  enviroguardPrediction: null,
  enviroguardHistory: [],
  slopeWatchPredictions: {},
  slopeWatchHistory: {},
  setEnviroguardPrediction: (p) =>
    set((s) => {
      const hist = [...s.enviroguardHistory, p];
      if (hist.length > AI_HISTORY_CAP) hist.splice(0, hist.length - AI_HISTORY_CAP);
      return { enviroguardPrediction: p, enviroguardHistory: hist };
    }),
  setSlopeWatchPrediction: (p) =>
    set((s) => {
      const next = { ...s.slopeWatchPredictions, [p.slope_id]: p };
      const histArr = [...(s.slopeWatchHistory[p.slope_id] ?? []), p];
      if (histArr.length > AI_HISTORY_CAP) histArr.splice(0, histArr.length - AI_HISTORY_CAP);
      return {
        slopeWatchPredictions: next,
        slopeWatchHistory: { ...s.slopeWatchHistory, [p.slope_id]: histArr },
      };
    }),
  reset: () =>
    set({
      enviroguardPrediction: null,
      enviroguardHistory: [],
      slopeWatchPredictions: {},
      slopeWatchHistory: {},
    }),
}));
