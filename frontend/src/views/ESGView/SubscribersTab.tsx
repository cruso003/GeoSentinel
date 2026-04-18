import { useEffect, useMemo, useState } from 'react';
import { Download, Search, Users } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { clsx } from '@/utils/clsx';
import { useUIStore } from '@/store/uiStore';
import { useAuthStore } from '@/store/authStore';
import { MOCK_SITE } from '@/mock/site';
import { ApiError } from '@/api/client';
import { listSubscribers, type SubscriberRow } from '@/api/notifications';

function isMockSession(): boolean {
  const token = useAuthStore.getState().session?.access_token ?? '';
  return token.startsWith('mock-');
}

function mockRows(): SubscriberRow[] {
  return [
    {
      user_id: 'u-esg',
      user_email: 'admin@geosentinel.dev',
      user_name: 'ESG Admin',
      site_id: MOCK_SITE.id,
      channel: 'email',
      min_severity: 'CRITICAL',
      active: true,
    },
    {
      user_id: 'u-esg',
      user_email: 'admin@geosentinel.dev',
      user_name: 'ESG Admin',
      site_id: MOCK_SITE.id,
      channel: 'sms',
      min_severity: 'EVACUATION',
      active: true,
    },
    {
      user_id: 'u-op',
      user_email: 'operator@geosentinel.dev',
      user_name: 'Site Operator',
      site_id: MOCK_SITE.id,
      channel: 'email',
      min_severity: 'WARNING',
      active: true,
    },
    {
      user_id: 'u-op',
      user_email: 'operator@geosentinel.dev',
      user_name: 'Site Operator',
      site_id: MOCK_SITE.id,
      channel: 'sms',
      min_severity: 'CRITICAL',
      active: false,
    },
  ];
}

function toCsv(rows: SubscriberRow[]): string {
  const header = ['user_email', 'user_name', 'site_id', 'channel', 'min_severity', 'active'];
  const esc = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const lines = rows.map((r) =>
    [r.user_email, r.user_name, r.site_id, r.channel, r.min_severity, String(r.active)]
      .map(esc)
      .join(','),
  );
  return [header.join(','), ...lines].join('\n');
}

export function SubscribersTab() {
  const light = useUIStore((s) => s.esgLightTheme);
  const mock = useUIStore((s) => s.mockMode) || isMockSession();
  const [rows, setRows] = useState<SubscriberRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [siteFilter, setSiteFilter] = useState<string>('');
  const [channelFilter, setChannelFilter] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = mock ? mockRows() : await listSubscribers();
        if (!cancelled) setRows(data);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError && e.status === 403
              ? 'You need ESG admin role to view subscribers.'
              : e instanceof Error
                ? e.message
                : 'Failed to load subscribers',
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [mock]);

  const sites = useMemo(() => Array.from(new Set(rows.map((r) => r.site_id))).sort(), [rows]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (siteFilter && r.site_id !== siteFilter) return false;
      if (channelFilter && r.channel !== channelFilter) return false;
      if (!q) return true;
      return (
        r.user_email.toLowerCase().includes(q) ||
        r.user_name.toLowerCase().includes(q)
      );
    });
  }, [rows, query, siteFilter, channelFilter]);

  const activeCount = filtered.filter((r) => r.active).length;

  function exportCsv() {
    const csv = toCsv(filtered);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `geosentinel-subscribers-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4 p-4">
      <Card
        title={
          <span className="flex items-center gap-2">
            <Users className="h-4 w-4" /> Subscribers
          </span>
        }
        subtitle={`${filtered.length} rows · ${activeCount} active${mock ? ' · mock data' : ''}`}
        actions={
          <button
            type="button"
            className="gs-button text-xs"
            onClick={exportCsv}
            disabled={filtered.length === 0}
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        }
      >
        <div className="mb-3 grid gap-2 md:grid-cols-3">
          <label className="relative text-xs">
            <span className="sr-only">Search by user</span>
            <Search
              className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name or email"
              className={clsx(
                'w-full rounded-md border px-7 py-1.5 text-sm',
                light
                  ? 'border-slate-300 bg-white text-slate-900 placeholder:text-slate-400'
                  : 'border-bg-line bg-bg-deep text-slate-100 placeholder:text-slate-500',
              )}
            />
          </label>
          <select
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value)}
            aria-label="Filter by site"
            className={clsx(
              'rounded-md border px-2 py-1.5 text-sm',
              light
                ? 'border-slate-300 bg-white text-slate-900'
                : 'border-bg-line bg-bg-deep text-slate-100',
            )}
          >
            <option value="">All sites</option>
            {sites.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            aria-label="Filter by channel"
            className={clsx(
              'rounded-md border px-2 py-1.5 text-sm',
              light
                ? 'border-slate-300 bg-white text-slate-900'
                : 'border-bg-line bg-bg-deep text-slate-100',
            )}
          >
            <option value="">All channels</option>
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="push">Push</option>
          </select>
        </div>

        {loading ? (
          <div className="animate-pulse py-6 text-sm opacity-60">Loading…</div>
        ) : error ? (
          <div
            role="alert"
            className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
          >
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-6 text-center text-sm opacity-60">No subscribers match the filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className={clsx('text-left text-xs uppercase tracking-wider', light ? 'text-slate-500' : 'text-slate-500')}>
                <tr>
                  <th className="py-2 pr-3">User</th>
                  <th className="py-2 pr-3">Email</th>
                  <th className="py-2 pr-3">Site</th>
                  <th className="py-2 pr-3">Channel</th>
                  <th className="py-2 pr-3">Min Severity</th>
                  <th className="py-2 pr-3">Active</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, i) => (
                  <tr
                    key={`${r.user_id}-${r.site_id}-${r.channel}-${i}`}
                    className={clsx('border-t', light ? 'border-slate-200' : 'border-bg-line')}
                  >
                    <td className="py-1.5 pr-3">{r.user_name}</td>
                    <td className="py-1.5 pr-3 opacity-80">{r.user_email}</td>
                    <td className="py-1.5 pr-3 font-mono text-xs opacity-80">{r.site_id}</td>
                    <td className="py-1.5 pr-3 uppercase tracking-wide text-xs">{r.channel}</td>
                    <td className="py-1.5 pr-3 uppercase tracking-wide text-xs">{r.min_severity}</td>
                    <td className="py-1.5 pr-3">
                      <span
                        className={clsx(
                          'gs-pill',
                          r.active
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-slate-500/20 text-slate-400',
                        )}
                      >
                        {r.active ? 'on' : 'off'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
