import { useState } from 'react';
import { ChevronDown, Cpu } from 'lucide-react';
import { useUIStore } from '@/store/uiStore';
import { SCENARIOS } from '@/mock/scenarios';
import type { Scenario } from '@/types';

export function ScenarioControl() {
  const mockMode = useUIStore((s) => s.mockMode);
  const scenario = useUIStore((s) => s.activeScenario);
  const setScenario = useUIStore((s) => s.setActiveScenario);
  const startedAt = useUIStore((s) => s.scenarioStartedAt);
  const [open, setOpen] = useState(false);

  if (!mockMode) return null;
  const elapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toString().padStart(2, '0');

  return (
    <div className="fixed bottom-4 right-4 z-40">
      <div className="gs-card w-72 px-3 py-2 text-xs">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-2 text-left"
        >
          <span className="flex items-center gap-2 font-semibold text-slate-200">
            <Cpu className="h-4 w-4 text-brand-accent" />
            Scenario: {SCENARIOS[scenario].label}
          </span>
          <ChevronDown className={`h-4 w-4 transition ${open ? 'rotate-180' : ''}`} />
        </button>
        <div className="mt-1 text-slate-400">
          Elapsed {m}:{s} · {SCENARIOS[scenario].description}
        </div>
        {open && (
          <ul className="mt-2 space-y-1 border-t border-bg-line pt-2">
            {(Object.keys(SCENARIOS) as Scenario[]).map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => {
                    setScenario(key);
                    setOpen(false);
                  }}
                  className={`block w-full rounded px-2 py-1 text-left transition hover:bg-bg-line ${
                    key === scenario ? 'bg-bg-line text-white' : 'text-slate-300'
                  }`}
                >
                  {SCENARIOS[key].label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
