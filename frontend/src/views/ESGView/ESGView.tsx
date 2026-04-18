import { NavLink, Route, Routes } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useUIStore } from '@/store/uiStore';
import { clsx } from '@/utils/clsx';
import { ComplianceTab } from './ComplianceTab';
import { SubscribersTab } from './SubscribersTab';

const TABS = [
  { to: '/esg', label: 'Compliance', end: true },
  { to: '/esg/subscribers', label: 'Subscribers' },
];

export function ESGView() {
  const light = useUIStore((s) => s.esgLightTheme);
  const toggleTheme = useUIStore((s) => s.toggleEsgTheme);

  return (
    <div className={clsx('flex h-screen w-full overflow-hidden', light ? 'bg-slate-50 text-slate-900' : 'bg-bg-deep text-slate-100')}>
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-auto">
        <header
          className={clsx(
            'flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3',
            light ? 'border-slate-200 bg-white' : 'border-bg-line bg-bg-panel',
          )}
        >
          <div>
            <h1 className="text-lg font-bold">ESG Compliance Dashboard</h1>
            <p className="text-xs opacity-70">Tokadeh Pilot Site · Reporting period: last 30 days</p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className={clsx(
              'flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium',
              light ? 'border border-slate-300 bg-slate-100 text-slate-700' : 'border border-bg-line bg-bg-card text-slate-200',
            )}
          >
            {light ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
            {light ? 'Dark' : 'Light'} theme
          </button>
        </header>

        <nav
          className={clsx(
            'flex gap-1 border-b px-4',
            light ? 'border-slate-200 bg-white' : 'border-bg-line bg-bg-panel',
          )}
          aria-label="ESG sections"
        >
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                clsx(
                  'relative px-3 py-2 text-sm font-medium',
                  isActive
                    ? 'text-brand-accent after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:bg-brand-primary'
                    : light
                      ? 'text-slate-600 hover:text-slate-900'
                      : 'text-slate-400 hover:text-slate-100',
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>

        <Routes>
          <Route index element={<ComplianceTab />} />
          <Route path="subscribers" element={<SubscribersTab />} />
        </Routes>
      </main>
    </div>
  );
}
