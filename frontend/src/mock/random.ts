// Deterministic-ish utilities for the mock data generators.
// Not crypto-grade — deterministic per (seed, t) so charts look stable
// across renders.

export function mulberry32(seed: number) {
  let s = seed | 0;
  return function () {
    s = (s + 0x6d2b79f5) | 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
}

// Cheap noise from a node id + timestamp (ms).
export function noiseFor(nodeId: string, t: number, salt = 0): number {
  let h = salt;
  for (let i = 0; i < nodeId.length; i++) h = (h * 31 + nodeId.charCodeAt(i)) >>> 0;
  // Wrap t into a few different frequencies for non-flat noise.
  const a = Math.sin((t / 60_000) * 0.7 + h);
  const b = Math.sin((t / 600_000) * 0.3 + h * 1.7);
  const c = Math.sin((t / 3_600_000) * 0.13 + h * 0.9);
  return (a * 0.5 + b * 0.3 + c * 0.2);
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// Smoothstep transition 0..1
export function smooth(t: number): number {
  const x = clamp(t, 0, 1);
  return x * x * (3 - 2 * x);
}

// Returns whether the current month is West-African wet season (May–October).
export function isWetSeason(date: Date): boolean {
  const m = date.getUTCMonth() + 1;
  return m >= 5 && m <= 10;
}

// Diurnal factor 0..1 peaking around local solar noon (UTC for Liberia ≈ noon local).
export function diurnalFactor(date: Date): number {
  const hour = date.getUTCHours() + date.getUTCMinutes() / 60;
  return 0.5 - 0.5 * Math.cos(((hour - 6) / 24) * Math.PI * 2);
}
