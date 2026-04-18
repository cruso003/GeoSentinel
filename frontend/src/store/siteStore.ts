import { create } from 'zustand';
import { getMySites, type MySite } from '@/api/notifications';
import { MOCK_SITE } from '@/mock/site';
import { useUIStore } from './uiStore';
import { useAuthStore } from './authStore';

// The backend exposes /me/sites for authenticated users (see
// backend/app/api/v1/notifications.py). In mock mode the frontend falls
// back to the single Tokadeh site so the switcher still renders plausibly.

const MOCK_SITES: MySite[] = [
  {
    id: MOCK_SITE.id,
    name: MOCK_SITE.name,
    region: MOCK_SITE.region,
    country: MOCK_SITE.country,
    centroid: MOCK_SITE.centroid,
  },
];

interface SiteState {
  sites: MySite[];
  loaded: boolean;
  loading: boolean;
  error: string | null;
  loadSites: () => Promise<void>;
  reset: () => void;
}

function isMockSession(): boolean {
  const token = useAuthStore.getState().session?.access_token ?? '';
  return token.startsWith('mock-');
}

export const useSiteStore = create<SiteState>()((set, get) => ({
  sites: [],
  loaded: false,
  loading: false,
  error: null,
  loadSites: async () => {
    if (get().loading) return;
    set({ loading: true, error: null });

    const mock = useUIStore.getState().mockMode || isMockSession();
    try {
      const sites = mock ? MOCK_SITES : await getMySites();
      set({ sites, loaded: true, loading: false });
      reconcileActiveSite(sites);
    } catch (err) {
      // Fail soft: keep whatever sites the store already had and mark the
      // error. The switcher will show a stale list rather than disappear.
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Could not load sites.',
      });
    }
  },
  reset: () => set({ sites: [], loaded: false, loading: false, error: null }),
}));

// If the persisted activeSiteId isn't in the accessible list (e.g. user
// switched accounts, site was removed), pin the first accessible site.
function reconcileActiveSite(sites: MySite[]): void {
  if (sites.length === 0) return;
  const ui = useUIStore.getState();
  if (!sites.some((s) => s.id === ui.activeSiteId)) {
    ui.setActiveSiteId(sites[0].id);
  }
}
