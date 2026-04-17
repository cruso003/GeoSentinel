import { clsx } from '@/utils/clsx';

type Tone = 'good' | 'caution' | 'alert' | 'critical' | 'info' | 'neutral' | 'evacuation';

const TONE_CLASS: Record<Tone, string> = {
  good: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  caution: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  alert: 'bg-red-500/15 text-red-300 ring-red-500/30',
  critical: 'bg-red-600/20 text-red-200 ring-red-500/40 animate-pulse-slow',
  info: 'bg-blue-500/15 text-blue-300 ring-blue-500/30',
  neutral: 'bg-slate-600/20 text-slate-300 ring-slate-500/30',
  evacuation: 'bg-violet-600/20 text-violet-200 ring-violet-500/40 animate-pulse-alarm',
};

export function Pill({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={clsx('gs-pill ring-1', TONE_CLASS[tone], className)}>{children}</span>
  );
}
