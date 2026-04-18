import { Link, useLocation } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Boxes,
  Compass,
  CpuIcon,
  Droplets,
  LayoutDashboard,
  LogOut,
  Mountain,
  UserCog,
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useAlertStore } from '@/store/alertStore';
import { SiteSwitcher } from './SiteSwitcher';
import { clsx } from '@/utils/clsx';

const NAV = [
  { to: '/operations', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/operations/environmental', label: 'Environmental', icon: Droplets },
  { to: '/operations/geotechnical', label: 'Geotechnical', icon: Mountain },
  { to: '/operations/twin', label: 'Digital Twin', icon: Boxes },
  { to: '/operations/alerts', label: 'Alerts', icon: AlertTriangle },
  { to: '/operations/nodes', label: 'Node Health', icon: CpuIcon },
  { to: '/operations/profile', label: 'Profile', icon: UserCog },
];

export function Sidebar() {
  const location = useLocation();
  const session = useAuthStore((s) => s.session);
  const logout = useAuthStore((s) => s.logout);
  const activeAlerts = useAlertStore((s) => s.activeAlerts);
  const critical = useAlertStore((s) => s.criticalAlertActive || s.evacuationAlertActive);

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-bg-line bg-bg-panel md:flex">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-primary/20 text-brand-accent">
          <Compass className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-bold text-white">GeoSentinel</div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Sentinel Ops</div>
        </div>
      </div>

      <SiteSwitcher className="px-3" />

      <nav className="mt-4 flex-1 space-y-0.5 px-2">
        {NAV.map(({ to, label, icon: Icon, end }) => {
          const active = end
            ? location.pathname === to
            : location.pathname.startsWith(to);
          const isAlerts = to.endsWith('/alerts');
          return (
            <Link
              key={to}
              to={to}
              className={clsx(
                'group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition',
                active
                  ? 'bg-brand-primary/15 text-white ring-1 ring-brand-primary/40'
                  : 'text-slate-300 hover:bg-bg-line/60 hover:text-white',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {isAlerts && activeAlerts.length > 0 && (
                <span
                  className={clsx(
                    'rounded-full px-1.5 py-0.5 text-[10px] font-bold',
                    critical
                      ? 'bg-red-500 text-white animate-pulse-alarm'
                      : 'bg-amber-500/80 text-amber-950',
                  )}
                >
                  {activeAlerts.length}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-bg-line px-3 py-3">
        <Link
          to="/esg"
          className="mb-2 flex items-center gap-2 rounded-md border border-bg-line px-2 py-1.5 text-xs text-slate-300 hover:border-brand-primary hover:text-white"
        >
          <Activity className="h-3.5 w-3.5" /> ESG Dashboard
        </Link>
        <div className="flex items-center gap-2 px-1">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-bg-line text-xs font-bold text-slate-200">
            {session?.user.name.charAt(0) ?? '?'}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs text-slate-200">{session?.user.name ?? 'Guest'}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              {session?.user.role.replace('_', ' ') ?? '—'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              void logout();
            }}
            title="Sign out"
            className="rounded-md p-1.5 text-slate-400 hover:bg-bg-line hover:text-white"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
