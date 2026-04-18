import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ChevronDown, Compass, Droplets, Mountain, Wind } from 'lucide-react';
import { useAIStore } from '@/store/aiStore';
import { useSensorStore } from '@/store/sensorStore';
import { fmtAgo } from '@/utils/format';
import { checkCompliance } from '@/utils/ifc-thresholds';
import { clsx } from '@/utils/clsx';
import type { PlainStatus } from '@/types';
import { OptInCard } from './OptInCard';

const TONE_BG: Record<PlainStatus, string> = {
  GOOD: 'bg-emerald-50 ring-emerald-300 text-emerald-900',
  CAUTION: 'bg-amber-50 ring-amber-300 text-amber-900',
  ALERT: 'bg-red-50 ring-red-300 text-red-900',
  CRITICAL: 'bg-red-100 ring-red-400 text-red-950',
};

const TONE_DOT: Record<PlainStatus, string> = {
  GOOD: 'bg-emerald-500',
  CAUTION: 'bg-amber-500',
  ALERT: 'bg-red-500',
  CRITICAL: 'bg-red-600 animate-pulse',
};

interface StatusCard {
  key: 'water' | 'air' | 'ground';
  title: string;
  status: PlainStatus;
  primary: string;
  detail: string;
  updated: string;
  icon: React.ReactNode;
}

export function CommunityView() {
  const { siteId = 'tokadeh-pilot' } = useParams();
  const env = useSensorStore((s) => s.latestEnvReadings);
  const slopes = useAIStore((s) => s.slopeWatchPredictions);

  const cards: StatusCard[] = useMemo(() => {
    const env03 = env['ENV-03'];
    const env01 = env['ENV-01'];
    const ph = env03?.ph ?? env01?.ph ?? null;
    const turb = env03?.turbidity ?? env01?.turbidity ?? null;
    const phC = checkCompliance('ph', ph);
    const turbC = checkCompliance('turbidity', turb);
    const waterStatus: PlainStatus = phC.exceeded || turbC.exceeded ? 'ALERT' : phC.near_limit || turbC.near_limit ? 'CAUTION' : 'GOOD';

    const pm25 = env01?.pm25 ?? null;
    const pmC = checkCompliance('pm25', pm25);
    const airStatus: PlainStatus = pmC.exceeded ? 'ALERT' : pmC.near_limit ? 'CAUTION' : 'GOOD';

    const tier = Object.values(slopes).reduce<string>((acc, s) => {
      const o = ['NORMAL', 'WATCH', 'WARNING', 'CRITICAL', 'EVACUATION'];
      return o.indexOf(s.alert_tier) > o.indexOf(acc) ? s.alert_tier : acc;
    }, 'NORMAL');
    const groundStatus: PlainStatus =
      tier === 'EVACUATION' || tier === 'CRITICAL'
        ? 'CRITICAL'
        : tier === 'WARNING'
          ? 'ALERT'
          : tier === 'WATCH'
            ? 'CAUTION'
            : 'GOOD';

    return [
      {
        key: 'water',
        title: 'Drinking Water',
        status: waterStatus,
        primary: waterStatus === 'GOOD' ? 'SAFE' : waterStatus === 'CAUTION' ? 'CAUTION' : 'DO NOT USE',
        detail:
          waterStatus === 'GOOD'
            ? 'Water at the community intake points is within safe limits.'
            : waterStatus === 'CAUTION'
              ? 'Some readings are approaching limits. Boil water before drinking.'
              : 'Do not use water for drinking or cooking until further notice.',
        updated: env03?.timestamp ?? new Date().toISOString(),
        icon: <Droplets className="h-8 w-8" />,
      },
      {
        key: 'air',
        title: 'Air Quality',
        status: airStatus,
        primary: airStatus === 'GOOD' ? 'GOOD' : airStatus === 'CAUTION' ? 'MODERATE' : 'POOR',
        detail:
          airStatus === 'GOOD'
            ? 'Air quality is good for outdoor activity.'
            : 'Sensitive groups should reduce prolonged outdoor exertion.',
        updated: env01?.timestamp ?? new Date().toISOString(),
        icon: <Wind className="h-8 w-8" />,
      },
      {
        key: 'ground',
        title: 'Ground Stability',
        status: groundStatus,
        primary:
          groundStatus === 'GOOD'
            ? 'STABLE'
            : groundStatus === 'CAUTION'
              ? 'MONITORING'
              : 'ALERT',
        detail:
          groundStatus === 'CRITICAL'
            ? 'Avoid the marked exclusion zone around the mine pit.'
            : groundStatus === 'ALERT'
              ? 'Increased monitoring active. Stay clear of slope edges.'
              : 'Slopes are stable.',
        updated: new Date().toISOString(),
        icon: <Mountain className="h-8 w-8" />,
      },
    ];
  }, [env, slopes]);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-4 py-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-emerald-600 text-white">
            <Compass className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold">GeoSentinel</h1>
            <p className="text-xs text-slate-600">
              Environmental Monitoring · Tokadeh Area, Nimba County
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-4 p-4">
        {cards.map((c) => (
          <CommunityCard key={c.key} card={c} />
        ))}

        <OptInCard siteId={siteId} />

        <IncidentHistory />

        <footer className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">Contact & report concerns</h3>
          <ul className="mt-2 space-y-1">
            <li>ArcelorMittal Liberia Environmental Hotline: <strong>+231-77-000-0000</strong></li>
            <li>EPA Liberia (Nimba field office): <strong>+231-77-000-1111</strong></li>
            <li>GeoSentinel report submission: <strong>report@geosentinel.app</strong></li>
          </ul>
        </footer>
      </main>
    </div>
  );
}

function CommunityCard({ card }: { card: StatusCard }) {
  const [open, setOpen] = useState(false);
  return (
    <section className={clsx('rounded-2xl p-4 shadow-sm ring-1', TONE_BG[card.status])}>
      <div className="flex items-start gap-4">
        <div>{card.icon}</div>
        <div className="flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider opacity-70">{card.title}</div>
          <div className="mt-0.5 flex items-center gap-2">
            <span className={clsx('h-3 w-3 rounded-full', TONE_DOT[card.status])} />
            <span className="text-2xl font-bold">{card.primary}</span>
          </div>
          <p className="mt-1 text-sm">{card.detail}</p>
          <div className="mt-1 text-[11px] opacity-70">Last checked {fmtAgo(card.updated)}</div>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mt-2 inline-flex items-center gap-1 text-xs font-semibold underline"
          >
            Learn more
            <ChevronDown className={clsx('h-3 w-3 transition', open && 'rotate-180')} />
          </button>
          {open && (
            <p className="mt-2 text-xs opacity-80">
              Readings are taken every five minutes from sensors maintained by the GeoSentinel
              programme and reviewed by community-trained monitors.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function IncidentHistory() {
  const incidents = [
    { date: '2026-04-10', kind: 'Air', desc: 'Brief PM2.5 spike (haul-truck convoy)', status: 'Resolved' },
    { date: '2026-03-22', kind: 'Water', desc: 'Turbidity exceedance after heavy rainfall', status: 'Resolved' },
    { date: '2026-02-14', kind: 'Ground', desc: 'Minor slope movement, no public impact', status: 'Resolved' },
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">Past 12-month incidents</h3>
      <ul className="mt-2 divide-y divide-slate-200 text-sm">
        {incidents.map((i, idx) => (
          <li key={idx} className="flex items-center justify-between py-2">
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-500">{i.date} · {i.kind}</div>
              <div>{i.desc}</div>
            </div>
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
              {i.status}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
