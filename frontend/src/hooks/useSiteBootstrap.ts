import { useEffect } from 'react';
import { useSiteStore } from '@/store/siteStore';
import { useAuthStore } from '@/store/authStore';
import { useUIStore } from '@/store/uiStore';

// Re-fetch /me/sites whenever the auth session or mock-mode flag changes so
// the switcher always reflects what the current user can access.
export function useSiteBootstrap(): void {
  const token = useAuthStore((s) => s.session?.access_token ?? null);
  const mockMode = useUIStore((s) => s.mockMode);
  const load = useSiteStore((s) => s.loadSites);
  const reset = useSiteStore((s) => s.reset);

  useEffect(() => {
    if (!token && !mockMode) {
      // Logged out, real mode — no /me/sites to fetch.
      reset();
      return;
    }
    void load();
  }, [token, mockMode, load, reset]);
}
