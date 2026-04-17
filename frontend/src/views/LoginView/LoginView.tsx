import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mountain, ShieldCheck, Users } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import type { UserRole } from '@/types';

const QUICK_ROLES: { role: UserRole; label: string; desc: string; icon: React.ReactNode }[] = [
  {
    role: 'operator',
    label: 'Site Operator',
    desc: 'Live sensor monitoring and alert acknowledgement.',
    icon: <Mountain className="h-5 w-5" />,
  },
  {
    role: 'esg_admin',
    label: 'ESG Admin',
    desc: 'Compliance dashboards, IFC reports, audit log.',
    icon: <ShieldCheck className="h-5 w-5" />,
  },
  {
    role: 'community',
    label: 'Community',
    desc: 'Public environmental health portal.',
    icon: <Users className="h-5 w-5" />,
  },
];

export function LoginView() {
  const loginMock = useAuthStore((s) => s.loginAsMock);
  const navigate = useNavigate();
  const [email, setEmail] = useState('operator@geosentinel.app');
  const [password, setPassword] = useState('operator123');

  const onMockLogin = (role: UserRole) => {
    loginMock(role);
    navigate('/');
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Phase 1: derive role from seed credentials (Spec 15.3).
    if (email.startsWith('admin')) onMockLogin('esg_admin');
    else if (email.startsWith('community')) onMockLogin('community');
    else onMockLogin('operator');
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-bg-deep via-bg-panel to-bg-deep px-4">
      <div className="grid w-full max-w-4xl grid-cols-1 gap-6 md:grid-cols-2">
        <section className="gs-card p-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-primary/20 text-brand-accent">
              <Mountain className="h-6 w-6" />
            </div>
            <div>
              <div className="text-xl font-bold tracking-tight text-white">GeoSentinel</div>
              <div className="text-xs text-slate-400">Environmental & Geohazard Intelligence</div>
            </div>
          </div>
          <form onSubmit={onSubmit} className="space-y-3">
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-400">Email</span>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="gs-input mt-1"
                type="email"
                autoComplete="email"
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-400">Password</span>
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="gs-input mt-1"
                type="password"
                autoComplete="current-password"
              />
            </label>
            <button type="submit" className="gs-button-primary mt-2 w-full justify-center">
              Sign in
            </button>
          </form>
          <p className="mt-4 text-xs text-slate-500">
            Phase 1 mock auth. Use seeded credentials from Spec §15.3 or pick a role on the right.
          </p>
        </section>
        <section className="gs-card p-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-200">Quick demo access</h2>
          <ul className="space-y-2">
            {QUICK_ROLES.map((r) => (
              <li key={r.role}>
                <button
                  type="button"
                  onClick={() => onMockLogin(r.role)}
                  className="flex w-full items-start gap-3 rounded-lg border border-bg-line bg-bg-card/60 p-3 text-left transition hover:border-brand-primary"
                >
                  <span className="mt-0.5 text-brand-accent">{r.icon}</span>
                  <span>
                    <span className="block text-sm font-semibold text-slate-100">{r.label}</span>
                    <span className="block text-xs text-slate-400">{r.desc}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
            Try <code className="font-mono">/?demo=true&amp;scenario=slope_warning</code> for the
            forum demo path.
          </div>
        </section>
      </div>
    </div>
  );
}
