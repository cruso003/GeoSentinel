import { Sparkles } from 'lucide-react';
import { useUIStore } from '@/store/uiStore';

export function DemoBanner() {
  const demo = useUIStore((s) => s.demoMode);
  if (!demo) return null;
  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-amber-500/95 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-amber-950">
      <Sparkles className="h-4 w-4" />
      DEMO MODE — Simulated Data
    </div>
  );
}
