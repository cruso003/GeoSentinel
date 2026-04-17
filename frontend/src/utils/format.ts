import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function fmtDateTime(iso: string): string {
  return format(parseISO(iso), 'yyyy-MM-dd HH:mm');
}

export function fmtTime(iso: string): string {
  return format(parseISO(iso), 'HH:mm:ss');
}

export function fmtAgo(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true });
}

export function fmtNum(v: number | null, digits = 2, fallback = '\u2014'): string {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback;
  return v.toFixed(digits);
}

export function fmtPct(v: number, digits = 0): string {
  return `${(v * 100).toFixed(digits)}%`;
}
