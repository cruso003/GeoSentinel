import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useSiteStore } from '@/store/siteStore';
import { useUIStore } from '@/store/uiStore';
import type { UserRole } from '@/types';
import { LoginView } from '@/views/LoginView/LoginView';
import { OperationsView } from '@/views/OperationsView/OperationsView';
import { ESGView } from '@/views/ESGView/ESGView';
import { CommunityView } from '@/views/CommunityView/CommunityView';
import { useDataEngine } from '@/hooks/useDataEngine';
import { useDemoParams } from '@/hooks/useDemoParams';
import { useSiteBootstrap } from '@/hooks/useSiteBootstrap';
import { DemoBanner } from '@/components/ui/DemoBanner';
import { ScenarioControl } from '@/components/ui/ScenarioControl';
import { CriticalAlertOverlay } from '@/components/alerts/CriticalAlertOverlay';
import { WalkthroughController } from '@/demo/WalkthroughController';

function ProtectedRoute({
  roles,
  children,
}: {
  roles: UserRole[];
  children: React.ReactNode;
}) {
  const session = useAuthStore((s) => s.session);
  if (!session) return <Navigate to="/login" replace />;
  if (!roles.includes(session.user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function HomeRedirect() {
  const session = useAuthStore((s) => s.session);
  const sites = useSiteStore((s) => s.sites);
  const activeSiteId = useUIStore((s) => s.activeSiteId);
  // Community landing uses activeSite; fall back to the first accessible
  // site, then to the legacy tokadeh-pilot id so the route still resolves
  // when /me/sites hasn't responded yet.
  const communitySiteId = activeSiteId || sites[0]?.id || 'tokadeh-pilot';
  if (!session) return <Navigate to={`/community/${communitySiteId}`} replace />;
  if (session.user.role === 'community') {
    return <Navigate to={`/community/${communitySiteId}`} replace />;
  }
  if (session.user.role === 'esg_admin') return <Navigate to="/esg" replace />;
  return <Navigate to="/operations" replace />;
}

export default function App() {
  useDemoParams();
  useSiteBootstrap();
  useDataEngine();

  return (
    <>
      <DemoBanner />
      <CriticalAlertOverlay />
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginView />} />
        <Route path="/community/:siteId" element={<CommunityView />} />
        <Route
          path="/operations/*"
          element={
            <ProtectedRoute roles={['operator', 'esg_admin']}>
              <OperationsView />
            </ProtectedRoute>
          }
        />
        <Route
          path="/esg/*"
          element={
            <ProtectedRoute roles={['esg_admin']}>
              <ESGView />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ScenarioControl />
      <WalkthroughController />
    </>
  );
}
