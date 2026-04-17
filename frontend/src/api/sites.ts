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
