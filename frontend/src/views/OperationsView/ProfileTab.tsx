import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Mail, Phone, Send, User as UserIcon } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { ApiError } from '@/api/client';
import {
  deleteSubscription,
  getMySites,
  getProfile,
  listMySubscriptions,
  sendTestAlert,
  updateProfile,
  upsertSubscription,
  type Channel,
  type MySite,
  type ProfileOut,
  type Severity,
  type Subscription,
} from '@/api/notifications';
import { useAuthStore } from '@/store/authStore';
import { useUIStore } from '@/store/uiStore';
import { MOCK_SITE } from '@/mock/site';
import { clsx } from '@/utils/clsx';

const CHANNELS: { value: Channel; label: string; icon: typeof Mail }[] = [
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'sms', label: 'SMS', icon: Phone },
];

const SEVERITIES: Severity[] = ['INFO', 'WARNING', 'CRITICAL', 'EVACUATION'];

type Banner = { kind: 'ok' | 'err'; text: string } | null;

function isMockSession(): boolean {
  const token = useAuthStore.getState().session?.access_token ?? '';
  return token.startsWith('mock-');
}

function findSubscription(
  subs: Subscription[],
  siteId: string,
  channel: Channel,
): Subscription | undefined {
  return subs.find((s) => s.site_id === siteId && s.channel === channel);
}

export function ProfileTab() {
  const mock = useUIStore((s) => s.mockMode) || isMockSession();
  const session = useAuthStore((s) => s.session);

  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [sites, setSites] = useState<MySite[]>([]);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState<Banner>(null);
  const [saving, setSaving] = useState(false);
  const [testingKey, setTestingKey] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');

  const flash = useCallback((b: NonNullable<Banner>) => {
    setBanner(b);
    window.setTimeout(() => setBanner(null), 4000);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        if (mock) {
          const u = session?.user;
          if (!u) return;
          const p: ProfileOut = {
            id: u.id,
            name: u.name,
            email: u.email,
            phone_number: null,
            role: u.role,
          };
          if (!cancelled) {
            setProfile(p);
            setName(p.name);
            setPhone('');
            setSites([
              {
                id: MOCK_SITE.id,
                name: MOCK_SITE.name,
                region: MOCK_SITE.region,
                country: MOCK_SITE.country,
                centroid: MOCK_SITE.centroid,
              },
            ]);
            setSubs([]);
          }
          return;
        }
        const [p, s, subList] = await Promise.all([
          getProfile(),
          getMySites(),
          listMySubscriptions(),
        ]);
        if (cancelled) return;
        setProfile(p);
        setName(p.name);
        setPhone(p.phone_number ?? '');
        setSites(s);
        setSubs(subList);
      } catch (e) {
        if (!cancelled) {
          flash({ kind: 'err', text: e instanceof Error ? e.message : 'Failed to load profile' });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [mock, session?.user, flash]);

  const dirty = useMemo(() => {
    if (!profile) return false;
    return name !== profile.name || phone !== (profile.phone_number ?? '');
  }, [profile, name, phone]);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    if (!profile || saving) return;
    setSaving(true);
    try {
      if (mock) {
        setProfile({ ...profile, name, phone_number: phone || null });
        flash({ kind: 'ok', text: 'Profile saved (mock mode — not persisted).' });
        return;
      }
      const updated = await updateProfile({
        name: name === profile.name ? undefined : name,
        phone_number: phone === (profile.phone_number ?? '') ? undefined : phone || null,
      });
      setProfile(updated);
      setPhone(updated.phone_number ?? '');
      flash({ kind: 'ok', text: 'Profile updated.' });
    } catch (e) {
      flash({
        kind: 'err',
        text:
          e instanceof ApiError
            ? e.message || `Error ${e.status}`
            : e instanceof Error
              ? e.message
              : 'Update failed',
      });
    } finally {
      setSaving(false);
    }
  }

  async function toggleChannel(site: MySite, channel: Channel) {
    const existing = findSubscription(subs, site.id, channel);
    if (mock) {
      if (existing) {
        setSubs((xs) => xs.filter((s) => s.id !== existing.id));
      } else {
        setSubs((xs) => [
          ...xs,
          {
            id: `mock-${site.id}-${channel}`,
            user_id: profile?.id ?? 'mock',
            site_id: site.id,
            channel,
            min_severity: 'CRITICAL',
            active: true,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      return;
    }
    try {
      if (existing && existing.active) {
        await deleteSubscription(existing.id);
        setSubs((xs) => xs.filter((s) => s.id !== existing.id));
      } else {
        const created = await upsertSubscription(site.id, channel, existing?.min_severity ?? 'CRITICAL', true);
        setSubs((xs) => {
          const rest = xs.filter((s) => !(s.site_id === site.id && s.channel === channel));
          return [...rest, created];
        });
      }
    } catch (e) {
      flash({ kind: 'err', text: e instanceof Error ? e.message : 'Subscription change failed' });
    }
  }

  async function changeSeverity(site: MySite, channel: Channel, severity: Severity) {
    const existing = findSubscription(subs, site.id, channel);
    if (mock) {
      setSubs((xs) =>
        existing
          ? xs.map((s) => (s.id === existing.id ? { ...s, min_severity: severity } : s))
          : xs,
      );
      return;
    }
    try {
      const updated = await upsertSubscription(site.id, channel, severity, existing?.active ?? true);
      setSubs((xs) => {
        const rest = xs.filter((s) => !(s.site_id === site.id && s.channel === channel));
        return [...rest, updated];
      });
    } catch (e) {
      flash({ kind: 'err', text: e instanceof Error ? e.message : 'Severity change failed' });
    }
  }

  async function sendTest(site: MySite, channel: Channel) {
    const key = `${site.id}-${channel}`;
    setTestingKey(key);
    try {
      if (mock) {
        await new Promise((r) => setTimeout(r, 400));
        flash({
          kind: 'ok',
          text: `Test ${channel} queued for ${site.name} (mock — not dispatched).`,
        });
        return;
      }
      await sendTestAlert(site.id, channel);
      flash({ kind: 'ok', text: `Test ${channel} dispatched to ${site.name}.` });
    } catch (e) {
      flash({
        kind: 'err',
        text:
          e instanceof ApiError && e.status === 400
            ? `Cannot send test: ${e.message}`
            : e instanceof Error
              ? e.message
              : 'Test dispatch failed',
      });
    } finally {
      setTestingKey(null);
    }
  }

  if (loading) {
    return (
      <div className="p-4">
        <div className="animate-pulse text-sm text-slate-400">Loading profile…</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-4 text-sm text-slate-400">Not signed in.</div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {banner && (
        <div
          role="status"
          aria-live="polite"
          className={clsx(
            'flex items-center gap-2 rounded-md border px-3 py-2 text-sm',
            banner.kind === 'ok'
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
              : 'border-red-500/40 bg-red-500/10 text-red-200',
          )}
        >
          {banner.kind === 'ok' ? (
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          ) : (
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
          )}
          <span>{banner.text}</span>
        </div>
      )}

      <Card title="Profile" subtitle="Update how you want to be reached.">
        <form onSubmit={saveProfile} className="grid gap-3 md:grid-cols-2">
          <label className="block text-xs">
            <span className="mb-1 flex items-center gap-1.5 text-slate-400">
              <UserIcon className="h-3.5 w-3.5" /> Name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="gs-input"
              autoComplete="name"
              maxLength={255}
              required
            />
          </label>
          <label className="block text-xs">
            <span className="mb-1 flex items-center gap-1.5 text-slate-400">
              <Mail className="h-3.5 w-3.5" /> Email
            </span>
            <input
              type="email"
              value={profile.email}
              readOnly
              className="gs-input cursor-not-allowed opacity-70"
              aria-readonly="true"
            />
          </label>
          <label className="block text-xs md:col-span-2">
            <span className="mb-1 flex items-center gap-1.5 text-slate-400">
              <Phone className="h-3.5 w-3.5" /> Phone (E.164, e.g. +231881234567)
            </span>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+231881234567"
              className="gs-input"
              inputMode="tel"
              autoComplete="tel"
              pattern="^\+?[0-9]{8,15}$"
              maxLength={20}
            />
          </label>
          <div className="md:col-span-2 flex items-center gap-3">
            <button
              type="submit"
              className="gs-button-primary disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!dirty || saving}
            >
              {saving ? 'Saving…' : 'Save profile'}
            </button>
            <span className="text-xs uppercase tracking-wider text-slate-500">
              Role: {profile.role.replace('_', ' ')}
            </span>
          </div>
        </form>
      </Card>

      <Card
        title="Notification preferences"
        subtitle="Per site × channel. Severity is the minimum level that triggers a notification."
      >
        {sites.length === 0 ? (
          <div className="text-sm text-slate-400">
            You have no site memberships. Ask an ESG admin to add you.
          </div>
        ) : (
          <div className="space-y-3">
            {sites.map((site) => (
              <div key={site.id} className="rounded-lg border border-bg-line bg-bg-deep/50 p-3">
                <div className="mb-2 flex items-baseline justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{site.name}</div>
                    <div className="text-[11px] uppercase tracking-wider text-slate-500">
                      {site.region} · {site.country}
                    </div>
                  </div>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {CHANNELS.map(({ value, label, icon: Icon }) => {
                    const sub = findSubscription(subs, site.id, value);
                    const on = Boolean(sub?.active);
                    const testKey = `${site.id}-${value}`;
                    const testing = testingKey === testKey;
                    const disableSms = value === 'sms' && !profile.phone_number && !mock;
                    return (
                      <div
                        key={value}
                        className="flex flex-wrap items-center gap-2 rounded-md border border-bg-line bg-bg-panel px-3 py-2"
                      >
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={() => void toggleChannel(site, value)}
                            disabled={disableSms}
                            aria-label={`Enable ${label} for ${site.name}`}
                            className="h-4 w-4 rounded border-bg-line bg-bg-deep"
                          />
                          <Icon className="h-4 w-4 text-slate-400" aria-hidden="true" />
                          <span>{label}</span>
                        </label>
                        <select
                          value={sub?.min_severity ?? 'CRITICAL'}
                          onChange={(e) => void changeSeverity(site, value, e.target.value as Severity)}
                          disabled={!on}
                          aria-label={`Minimum severity for ${label} on ${site.name}`}
                          className="gs-input w-auto text-xs disabled:opacity-50"
                        >
                          {SEVERITIES.map((sv) => (
                            <option key={sv} value={sv}>
                              ≥ {sv}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => void sendTest(site, value)}
                          disabled={!on || testing || disableSms}
                          className="gs-button ml-auto text-xs disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Send className="h-3.5 w-3.5" aria-hidden="true" />
                          {testing ? 'Sending…' : 'Send test'}
                        </button>
                        {disableSms && (
                          <div className="w-full text-[11px] text-amber-300">
                            Add a phone number above to enable SMS.
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
