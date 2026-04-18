import { Route, Routes } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import { StatusBar } from '@/components/layout/StatusBar';
import { OverviewTab } from './OverviewTab';
import { EnvironmentalTab } from './EnvironmentalTab';
import { GeotechnicalTab } from './GeotechnicalTab';
import { TwinTab } from './TwinTab';
import { AlertsTab } from './AlertsTab';
import { NodeHealthTab } from './NodeHealthTab';
import { ProfileTab } from './ProfileTab';

export function OperationsView() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg-deep">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">
        <StatusBar />
        <div className="flex-1 overflow-auto">
          <Routes>
            <Route index element={<OverviewTab />} />
            <Route path="environmental" element={<EnvironmentalTab />} />
            <Route path="geotechnical" element={<GeotechnicalTab />} />
            <Route path="twin" element={<TwinTab />} />
            <Route path="alerts" element={<AlertsTab />} />
            <Route path="nodes" element={<NodeHealthTab />} />
            <Route path="profile" element={<ProfileTab />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
