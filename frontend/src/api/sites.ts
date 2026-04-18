import type { MineSite, MineSlope, SensorNode } from '@/types';
import { api } from './client';
import { MOCK_SITE, MOCK_NODES, MOCK_SLOPES } from '@/mock/site';
import { useUIStore } from '@/store/uiStore';

function mockMode(): boolean {
  return useUIStore.getState().mockMode || import.meta.env.VITE_FORCE_MOCK === 'true';
}

export async function listSites(): Promise<MineSite[]> {
  if (mockMode()) return [MOCK_SITE];
  return api.get<MineSite[]>('/sites');
}

export async function getSite(siteId: string): Promise<MineSite> {
  if (mockMode()) return MOCK_SITE;
  return api.get<MineSite>(`/sites/${siteId}`);
}

export async function listNodes(siteId: string): Promise<SensorNode[]> {
  if (mockMode()) return MOCK_NODES;
  return api.get<SensorNode[]>(`/sites/${siteId}/nodes`);
}

export async function listSlopes(siteId: string): Promise<MineSlope[]> {
  if (mockMode()) return MOCK_SLOPES;
  return api.get<MineSlope[]>(`/sites/${siteId}/slopes`);
}

export interface InsarPoint {
  timestamp: string;
  displacement_mm: number;
}

export interface InsarSeries {
  site_id: string;
  slope_id: string;
  points: InsarPoint[];
  velocity_mm_yr: number | null;
  window_days: number;
}

export async function getSlopeInsar(
  siteId: string,
  slopeId: string,
  days = 90,
): Promise<InsarSeries> {
  if (mockMode()) return mockInsarSeries(siteId, slopeId, days);
  return api.get<InsarSeries>(`/sites/${siteId}/slopes/${slopeId}/insar?days=${days}`);
}

// Deterministic mock series so the chart renders in demo / walkthrough
// without the Celery weekly job having run. Shape mirrors what the
// synthetic manifest ingestion produces: a 6-day cadence, small drift,
// slope-specific offset. Velocity is fit-to-points — no free parameter.
function mockInsarSeries(siteId: string, slopeId: string, days: number): InsarSeries {
  const scenes = Math.max(6, Math.floor(days / 6));
  let h = 0;
  for (const ch of slopeId) h = (h * 131 + ch.charCodeAt(0)) & 0xffffffff;
  const offset = (((h % 1000) / 1000) - 0.5) * 6;
  const endDate = new Date();
  endDate.setUTCHours(12, 0, 0, 0);
  const final = slopeId.includes('tailings') ? 1.6 : 0.8; // mm over window
  const points: InsarPoint[] = [];
  for (let i = 0; i < scenes; i++) {
    const d = new Date(endDate);
    d.setUTCDate(d.getUTCDate() - 6 * (scenes - 1 - i));
    const frac = scenes > 1 ? i / (scenes - 1) : 0;
    points.push({
      timestamp: d.toISOString(),
      displacement_mm: Number((final * frac + offset).toFixed(3)),
    });
  }
  const first = points[0];
  const last = points[points.length - 1];
  const years =
    (new Date(last.timestamp).getTime() - new Date(first.timestamp).getTime()) /
    (365.25 * 24 * 3600 * 1000);
  const velocity = years > 0 ? (last.displacement_mm - first.displacement_mm) / years : 0;
  return {
    site_id: siteId,
    slope_id: slopeId,
    points,
    velocity_mm_yr: Number(velocity.toFixed(3)),
    window_days: days,
  };
}
