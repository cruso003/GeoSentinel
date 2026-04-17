import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '@/store/uiStore';
import { WALKTHROUGH_STEPS, WALKTHROUGH_TOTAL_MS, type WalkthroughStep } from './walkthrough';

// Auto-plays the demo when walkthroughActive is true in the UI store.
// Shows a bottom tooltip narrating each step and auto-navigates the router.
export function WalkthroughController() {
  const active = useUIStore((s) => s.walkthroughActive);
  const setWalkthroughActive = useUIStore((s) => s.setWalkthroughActive);
  const setActiveScenario = useUIStore((s) => s.setActiveScenario);
  const navigate = useNavigate();
  const [idx, setIdx] = useState(0);
  const startedRef = useRef<number | null>(null);

  const step: WalkthroughStep | undefined = WALKTHROUGH_STEPS[idx];
  const totalElapsedBefore = useMemo(
    () => WALKTHROUGH_STEPS.slice(0, idx).reduce((a, s) => a + s.durationMs, 0),
    [idx],
  );

  useEffect(() => {
    if (!active) {
      setIdx(0);
      startedRef.current = null;
      return;
    }
    if (!step) {
      setWalkthroughActive(false);
      return;
    }
    if (startedRef.current == null) startedRef.current = Date.now();
    if (step.scenario) setActiveScenario(step.scenario);
    navigate(step.route);
    const t = window.setTimeout(() => setIdx((i) => i + 1), step.durationMs);
    return () => window.clearTimeout(t);
  }, [active, idx, step, navigate, setActiveScenario, setWalkthroughActive]);

  if (!active || !step) return null;
  const progressPct = Math.min(
    100,
    Math.round(((totalElapsedBefore + step.durationMs / 2) / WALKTHROUGH_TOTAL_MS) * 100),
  );

  return (
    <div className="fixed bottom-6 left-1/2 z-[70] w-[min(720px,92vw)] -translate-x-1/2">
      <div className="gs-card border border-brand-primary/40 bg-bg-panel/95 px-5 py-4 shadow-2xl backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-brand-accent">
              Walkthrough · step {idx + 1} of {WALKTHROUGH_STEPS.length}
            </div>
            <div className="mt-1 text-base font-semibold text-white">{step.title}</div>
            <div className="mt-1 text-sm text-slate-300">{step.body}</div>
          </div>
          <button
            type="button"
            onClick={() => setWalkthroughActive(false)}
            className="gs-button shrink-0 text-xs"
          >
            Exit demo
          </button>
        </div>
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-bg-line">
          <div
            className="h-full bg-brand-primary transition-[width] duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
