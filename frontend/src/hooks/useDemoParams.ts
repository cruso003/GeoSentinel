import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Scenario } from '@/types';
import { useUIStore } from '@/store/uiStore';
import { useAuthStore } from '@/store/authStore';

const VALID_SCENARIOS: Scenario[] = [
  'normal',
  'rainfall_event',
  'tailings_seepage',
  'slope_warning',
  'node_offline',
];

// Reads ?demo=true&scenario=...&walkthrough=... from the URL and reflects
// it into UI store. Auto-creates a mock operator session for convenience.
export function useDemoParams(): void {
  const [params] = useSearchParams();
  const setDemoMode = useUIStore((s) => s.setDemoMode);
  const setMockMode = useUIStore((s) => s.setMockMode);
  const setActiveScenario = useUIStore((s) => s.setActiveScenario);
  const setWalkthroughActive = useUIStore((s) => s.setWalkthroughActive);
  const loginAsMock = useAuthStore((s) => s.loginAsMock);
  const isAuthed = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    const demo = params.get('demo');
    if (demo === 'walkthrough') {
      setDemoMode(true);
      setMockMode(true);
      setWalkthroughActive(true);
    } else if (demo === 'true') {
      setDemoMode(true);
      setMockMode(true);
    }
    const scenario = params.get('scenario');
    if (scenario && (VALID_SCENARIOS as string[]).includes(scenario)) {
      setActiveScenario(scenario as Scenario);
    }
    if ((demo === 'true' || demo === 'walkthrough') && !isAuthed) {
      loginAsMock('operator');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);
}
