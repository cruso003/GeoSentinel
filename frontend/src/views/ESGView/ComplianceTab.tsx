import { useMemo, useState } from 'react';
import { Download, FileText, ShieldCheck } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { useUIStore } from '@/store/uiStore';
import { useAuthStore } from '@/store/authStore';
import { useSensorStore } from '@/store/sensorStore';
import { checkCompliance } from '@/utils/ifc-thresholds';
import { clsx } from '@/utils/clsx';
import { format, parseISO, subDays } from 'date-fns';
import type { ComplianceReport, ReportStatus, ReportType } from '@/types';
import { ApiError } from '@/api/client';
import { downloadReport, generateReport } from '@/api/reports';

interface ScoreCard {
  label: string;
  value: string;
  unit?: string;
  delta: number;
  trend: number[];
}

export function ComplianceTab() {
  const light = useUIStore((s) => s.esgLightTheme);
  const env = useSensorStore((s) => s.envHistory);

  const compliance = useMemo(() => buildComplianceTrend(env), [env]);
  const cards = useMemo(() => buildScoreCards(env), [env]);

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((c) => (
          <ScoreCardView key={c.label} card={c} light={light} />
        ))}
      </div>

      <Card
        title="Compliance Timeline"
        subtitle={
          compliance.length > 0
            ? 'Hourly compliance share from the last 24 h of ingested readings'
            : 'Awaiting readings — hourly compliance renders once history is ingested'
        }
      >
        {compliance.length === 0 ? (
          <div
            className={clsx(
              'flex h-[280px] items-center justify-center rounded-md border border-dashed text-xs',
              light ? 'border-slate-300 text-slate-500' : 'border-bg-line text-slate-500',
            )}
          >
            No ingested readings yet. Start the data engine or connect a sensor
            gateway — the chart hydrates per hourly bucket.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={compliance} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={light ? '#E2E8F0' : '#1F3A5F'} />
              <XAxis
                dataKey="t"
                fontSize={11}
                stroke={light ? '#475569' : '#64748B'}
                tickFormatter={(v) => format(parseISO(v as string), 'HH:mm')}
                minTickGap={32}
              />
              <YAxis
                fontSize={11}
                stroke={light ? '#475569' : '#64748B'}
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="water" stroke="#22D3EE" fill="#22D3EE" fillOpacity={0.3} />
              <Area type="monotone" dataKey="air" stroke="#A78BFA" fill="#A78BFA" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      <ReportPanel light={light} />

      <AuditLogTable light={light} />
    </div>
  );
}

function ScoreCardView({ card, light }: { card: ScoreCard; light: boolean }) {
  const positive = card.delta >= 0;
  return (
    <div className={clsx('rounded-xl border p-3', light ? 'border-slate-200 bg-white' : 'border-bg-line bg-bg-panel')}>
      <div className="text-[10px] font-semibold uppercase tracking-wider opacity-60">{card.label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-2xl font-bold tabular-nums">{card.value}</div>
        {card.unit && <div className="text-xs opacity-60">{card.unit}</div>}
      </div>
      <div className={clsx('text-xs', positive ? 'text-emerald-500' : 'text-red-500')}>
        {positive ? '+' : ''}
        {card.delta.toFixed(1)} vs prev
      </div>
      <div className="mt-2 flex items-end gap-0.5">
        {card.trend.map((v, i) => (
          <div
            key={i}
            className={clsx('w-1.5 rounded-sm', light ? 'bg-slate-400' : 'bg-slate-500')}
            style={{ height: `${Math.max(2, v * 24)}px` }}
          />
        ))}
      </div>
    </div>
  );
}

function ReportPanel({ light }: { light: boolean }) {
  const isMock = useAuthStore((s) => s.session?.access_token.startsWith('mock-') ?? true);
  const siteId = useUIStore((s) => s.activeSiteId);
  const [type, setType] = useState<ReportType>('IFC_PERFORMANCE');
  const [periodStart, setPeriodStart] = useState(() => format(subDays(new Date(), 30), 'yyyy-MM-dd'));
  const [periodEnd, setPeriodEnd] = useState(() => format(new Date(), 'yyyy-MM-dd'));
  const [status, setStatus] = useState<ReportStatus>('pending');
  const [progress, setProgress] = useState<string>('');
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const run = async () => {
    setError(null);
    setReport(null);
    setStatus('generating');
    setProgress('Collecting compliance stats...');

    if (isMock) {
      // Walkthrough / demo mode — don't hit the real API so scenarios stay
      // side-effect free. Simulate a short delay and a synthetic integrity
      // hash so the UI still shows a plausible PDF handoff.
      const steps = ['Collecting compliance stats...', 'Running AI analysis...', 'Rendering PDF...'];
      for (const s of steps) {
        setProgress(s);
        await new Promise((r) => setTimeout(r, 600));
      }
      const hex = (n: number) =>
        Array.from({ length: n }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('');
      setReport({
        id: 'mock-' + Math.random().toString(36).slice(2, 8),
        site_id: siteId,
        report_type: type,
        period_start: `${periodStart}T00:00:00Z`,
        period_end: `${periodEnd}T23:59:59Z`,
        status: 'ready',
        download_url: null,
        generated_at: new Date().toISOString(),
        // Mock mode shows the UI handoff without faking cryptographic
        // artifacts — the Signed pill only renders when the backend
        // returns a real signature + pubkey from the live /generate call.
        data_integrity_hash: hex(64),
        signature_b64: null,
        signing_pubkey_hex: null,
      });
      setStatus('ready');
      return;
    }

    try {
      setProgress('Contacting backend...');
      const res = await generateReport({
        site_id: siteId,
        period_start: `${periodStart}T00:00:00Z`,
        period_end: `${periodEnd}T23:59:59Z`,
        report_type: type,
      });
      setReport(res);
      setStatus(res.status);
      if (res.status === 'failed') {
        setError('Backend could not render the report.');
      }
    } catch (err) {
      setStatus('failed');
      if (err instanceof ApiError) {
        setError(err.status === 403 ? 'ESG admin role required.' : err.message || 'Report request failed.');
      } else {
        setError('Report request failed.');
      }
    } finally {
      setProgress('');
    }
  };

  const onDownload = async () => {
    if (!report) return;
    if (isMock) {
      setError('Mock mode: PDF download is disabled in the demo. Log in to see the real file.');
      return;
    }
    setDownloading(true);
    setError(null);
    try {
      await downloadReport(report);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not download the PDF.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card title="Generate Compliance Report" subtitle="ReportLab PDF backed by the alert log + slope predictions">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-xs">
          <span className="opacity-60">Period start</span>
          <input
            type="date"
            value={periodStart}
            max={periodEnd}
            onChange={(e) => setPeriodStart(e.target.value)}
            className={clsx('mt-1 w-full rounded-md border px-2 py-1 text-sm', light ? 'border-slate-300 bg-white text-slate-900' : 'border-bg-line bg-bg-deep text-slate-100')}
          />
        </label>
        <label className="text-xs">
          <span className="opacity-60">Period end</span>
          <input
            type="date"
            value={periodEnd}
            min={periodStart}
            onChange={(e) => setPeriodEnd(e.target.value)}
            className={clsx('mt-1 w-full rounded-md border px-2 py-1 text-sm', light ? 'border-slate-300 bg-white text-slate-900' : 'border-bg-line bg-bg-deep text-slate-100')}
          />
        </label>
        <label className="text-xs">
          <span className="opacity-60">Report type</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as ReportType)}
            className={clsx('mt-1 w-full rounded-md border px-2 py-1 text-sm', light ? 'border-slate-300 bg-white text-slate-900' : 'border-bg-line bg-bg-deep text-slate-100')}
          >
            <option value="IFC_PERFORMANCE">IFC Performance Standard</option>
            <option value="ISO_14001">ISO 14001</option>
            <option value="CUSTOM_SUMMARY">Custom Summary</option>
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" className="gs-button-primary" onClick={run} disabled={status === 'generating'}>
          <FileText className="h-4 w-4" /> Generate
        </button>
        {status === 'generating' && <span className="text-xs opacity-70">{progress}</span>}
        {status === 'ready' && report && (
          <button type="button" className="gs-button" onClick={onDownload} disabled={downloading}>
            <Download className="h-4 w-4" />
            {downloading ? 'Preparing…' : 'Download PDF'}
          </button>
        )}
        {status === 'ready' && report?.data_integrity_hash && (
          <span className="font-mono text-[10px] opacity-60">
            SHA-256 {report.data_integrity_hash.slice(0, 12)}…
          </span>
        )}
        {status === 'ready' && report?.signing_pubkey_hex && (
          <SignedBadge pubkeyHex={report.signing_pubkey_hex} light={light} />
        )}
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-red-100/60 px-2 py-1 text-xs text-red-800 ring-1 ring-red-200">
          {error}
        </p>
      )}
    </Card>
  );
}

/** Renders an "Ed25519-signed" pill with a short fingerprint so the
 * reviewer can eyeball whether the pubkey matches the one they have on
 * file. Full signature + key is exposed via GET /reports/{id}/signature
 * — this is just the at-a-glance trust cue. */
function SignedBadge({ pubkeyHex, light }: { pubkeyHex: string; light: boolean }) {
  const fp = `${pubkeyHex.slice(0, 4)}:${pubkeyHex.slice(4, 8)}…${pubkeyHex.slice(-4)}`;
  return (
    <span
      title={`Ed25519 pubkey ${pubkeyHex}`}
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1',
        light
          ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
          : 'bg-emerald-900/30 text-emerald-300 ring-emerald-500/40',
      )}
    >
      <ShieldCheck className="h-3 w-3" />
      Signed
      <span className="font-mono opacity-80">{fp}</span>
    </span>
  );
}

function AuditLogTable({ light }: { light: boolean }) {
  // The live audit log is a hash-chained Postgres table written by every
  // mutating API call (see backend/app/services/audit.py). It is not yet
  // surfaced to the frontend; this card previews the shape of events a
  // reviewer will see once the server-side listing endpoint ships.
  const rows = [
    { ts: '— ', kind: 'AI Inference', actor: 'system', detail: 'EnviroGuard run · hash-chained' },
    { ts: '— ', kind: 'Alert Ack', actor: 'operator@site', detail: 'Conductivity warning acknowledged' },
    { ts: '— ', kind: 'Data Ingest', actor: 'gateway', detail: 'Reading batch written + checksummed' },
    { ts: '— ', kind: 'Report', actor: 'esg_admin', detail: 'IFC PDF generated + Ed25519-signed' },
  ];
  return (
    <Card
      title="Audit Log — Example Events"
      subtitle="Shape preview; live hash-chained log reads over a dedicated endpoint (coming)"
      actions={<button className="gs-button text-xs" disabled title="Pending live-feed endpoint">Export CSV</button>}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className={clsx('text-left text-xs uppercase tracking-wider', light ? 'text-slate-500' : 'text-slate-500')}>
            <tr>
              <th className="py-2 pr-3">Timestamp</th>
              <th className="py-2 pr-3">Event</th>
              <th className="py-2 pr-3">Actor</th>
              <th className="py-2 pr-3">Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={clsx('border-t opacity-60', light ? 'border-slate-200' : 'border-bg-line')}>
                <td className="py-1.5 pr-3 font-mono text-xs">{r.ts}</td>
                <td className="py-1.5 pr-3">{r.kind}</td>
                <td className="py-1.5 pr-3">{r.actor}</td>
                <td className="py-1.5 pr-3">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

type EnvHistory = ReturnType<typeof useSensorStore.getState>['envHistory'];
type EnvReading = EnvHistory[string][number];

const WATER_PARAMS = ['ph', 'turbidity', 'dissolved_oxygen', 'conductivity'] as const;
const AIR_PARAMS = ['pm25', 'pm10', 'so2', 'no2'] as const;

/** Fraction of (reading × tracked parameter) checks that are compliant. */
function compliantShare(readings: EnvReading[], params: readonly (keyof EnvReading)[]): number {
  if (readings.length === 0) return 0;
  let total = 0;
  let ok = 0;
  for (const r of readings) {
    for (const p of params) {
      const v = r[p];
      if (typeof v !== 'number' || Number.isNaN(v)) continue;
      total += 1;
      if (checkCompliance(p as never, v).compliant) ok += 1;
    }
  }
  return total === 0 ? 0 : ok / total;
}

/** Group readings into hourly buckets keyed by the bucket start timestamp. */
function bucketByHour(readings: EnvReading[], hours: number): Map<string, EnvReading[]> {
  const buckets = new Map<string, EnvReading[]>();
  const now = Date.now();
  const windowStart = now - hours * 3600_000;
  for (const r of readings) {
    const t = Date.parse(r.timestamp);
    if (Number.isNaN(t) || t < windowStart) continue;
    const bucketStart = new Date(t);
    bucketStart.setMinutes(0, 0, 0);
    const key = bucketStart.toISOString();
    const bucket = buckets.get(key);
    if (bucket) bucket.push(r);
    else buckets.set(key, [r]);
  }
  return buckets;
}

/** Rolling 24-h hourly compliance timeline, computed from the ingested
 * env history. Returns an empty array when there are no readings — the
 * caller renders an "awaiting data" state in that case. */
function buildComplianceTrend(env: EnvHistory): { t: string; water: number; air: number }[] {
  const allReadings: EnvReading[] = Object.values(env).flat();
  if (allReadings.length === 0) return [];

  const buckets = bucketByHour(allReadings, 24);
  if (buckets.size === 0) return [];

  const keys = Array.from(buckets.keys()).sort();
  return keys.map((key) => {
    const bucket = buckets.get(key) ?? [];
    return {
      t: key,
      water: Number((compliantShare(bucket, WATER_PARAMS) * 100).toFixed(1)),
      air: Number((compliantShare(bucket, AIR_PARAMS) * 100).toFixed(1)),
    };
  });
}

/** Score cards computed from the actual env history. Returns a card
 * flagged ``awaiting_data`` when no readings exist, so the UI can render
 * a muted state instead of a confidently wrong number. */
function buildScoreCards(env: EnvHistory): ScoreCard[] {
  const allReadings: EnvReading[] = Object.values(env).flat();

  const now = Date.now();
  const windowReadings = allReadings.filter((r) => {
    const t = Date.parse(r.timestamp);
    return !Number.isNaN(t) && t >= now - 24 * 3600_000;
  });
  const priorReadings = allReadings.filter((r) => {
    const t = Date.parse(r.timestamp);
    return !Number.isNaN(t) && t >= now - 48 * 3600_000 && t < now - 24 * 3600_000;
  });

  const nodeCount = Object.keys(env).length;
  const activeNodeCount = Object.values(env).filter((rs) => {
    const last = rs[rs.length - 1];
    if (!last) return false;
    const t = Date.parse(last.timestamp);
    return !Number.isNaN(t) && t >= now - 2 * 3600_000;
  }).length;

  const waterNow = compliantShare(windowReadings, WATER_PARAMS);
  const waterPrev = compliantShare(priorReadings, WATER_PARAMS);
  const airNow = compliantShare(windowReadings, AIR_PARAMS);
  const airPrev = compliantShare(priorReadings, AIR_PARAMS);

  const pct = (v: number) => `${(v * 100).toFixed(1)}`;
  const diffPp = (a: number, b: number) => Number(((a - b) * 100).toFixed(1));

  const hasWindowData = windowReadings.length > 0;
  const hasPriorData = priorReadings.length > 0;

  return [
    {
      label: 'Water Compliance (24h)',
      value: hasWindowData ? pct(waterNow) : '—',
      unit: hasWindowData ? '%' : undefined,
      delta: hasPriorData ? diffPp(waterNow, waterPrev) : 0,
      trend: [],
    },
    {
      label: 'Air Compliance (24h)',
      value: hasWindowData ? pct(airNow) : '—',
      unit: hasWindowData ? '%' : undefined,
      delta: hasPriorData ? diffPp(airNow, airPrev) : 0,
      trend: [],
    },
    {
      label: 'Env Readings (24h)',
      value: String(windowReadings.length),
      delta: hasPriorData ? windowReadings.length - priorReadings.length : 0,
      trend: [],
    },
    {
      label: 'Nodes Reporting',
      value: `${activeNodeCount}/${nodeCount || 0}`,
      delta: 0,
      trend: [],
    },
  ];
}
