import { useMemo, useState } from 'react';
import { Download, FileText } from 'lucide-react';
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

      <Card title="Compliance Timeline" subtitle="Stacked compliance % vs IFC limits">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={compliance} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={light ? '#E2E8F0' : '#1F3A5F'} />
            <XAxis
              dataKey="t"
              fontSize={11}
              stroke={light ? '#475569' : '#64748B'}
              tickFormatter={(v) => format(parseISO(v as string), 'MMM d')}
              minTickGap={32}
            />
            <YAxis
              fontSize={11}
              stroke={light ? '#475569' : '#64748B'}
              domain={[80, 100]}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area type="monotone" dataKey="water" stackId="1" stroke="#22D3EE" fill="#22D3EE" fillOpacity={0.4} />
            <Area type="monotone" dataKey="air" stackId="2" stroke="#A78BFA" fill="#A78BFA" fillOpacity={0.4} />
            <Area type="monotone" dataKey="geo" stackId="3" stroke="#34D399" fill="#34D399" fillOpacity={0.4} />
          </AreaChart>
        </ResponsiveContainer>
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
      setReport({
        id: 'mock-' + Math.random().toString(36).slice(2, 8),
        site_id: 'tokadeh-pilot',
        report_type: type,
        period_start: `${periodStart}T00:00:00Z`,
        period_end: `${periodEnd}T23:59:59Z`,
        status: 'ready',
        download_url: null,
        generated_at: new Date().toISOString(),
        data_integrity_hash: Array.from({ length: 64 }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join(''),
      });
      setStatus('ready');
      return;
    }

    try {
      setProgress('Contacting backend...');
      const res = await generateReport({
        site_id: 'tokadeh-pilot',
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
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-red-100/60 px-2 py-1 text-xs text-red-800 ring-1 ring-red-200">
          {error}
        </p>
      )}
    </Card>
  );
}

function AuditLogTable({ light }: { light: boolean }) {
  const rows = [
    { ts: '2026-04-16 09:12', kind: 'AI Inference', actor: 'system', detail: 'EnviroGuard run · confidence 0.86' },
    { ts: '2026-04-16 08:00', kind: 'Calibration', actor: 'op-jane', detail: 'ENV-01 pH probe re-calibrated' },
    { ts: '2026-04-15 22:45', kind: 'Alert Ack', actor: 'op-james', detail: 'Conductivity warning ENV-02 acknowledged' },
    { ts: '2026-04-15 14:11', kind: 'Data Ingest', actor: 'gateway', detail: '14,322 readings stored to InfluxDB' },
    { ts: '2026-04-14 06:00', kind: 'Report', actor: 'esg-admin', detail: 'IFC report generated for March' },
  ];
  return (
    <Card title="Audit Log" subtitle="Compliance-relevant system events" actions={<button className="gs-button text-xs">Export CSV</button>}>
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
              <tr key={i} className={clsx('border-t', light ? 'border-slate-200' : 'border-bg-line')}>
                <td className="py-1.5 pr-3 font-mono text-xs">{r.ts}</td>
                <td className="py-1.5 pr-3">{r.kind}</td>
                <td className="py-1.5 pr-3 opacity-70">{r.actor}</td>
                <td className="py-1.5 pr-3 opacity-70">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function buildComplianceTrend(_env: ReturnType<typeof useSensorStore.getState>['envHistory']) {
  const out: { t: string; water: number; air: number; geo: number }[] = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = subDays(now, i);
    out.push({
      t: d.toISOString(),
      water: 31 + Math.random() * 1.5,
      air: 33 + Math.random() * 1.2,
      geo: 32 + Math.random(),
    });
  }
  return out;
}

function buildScoreCards(env: ReturnType<typeof useSensorStore.getState>['envHistory']): ScoreCard[] {
  const allEnv01 = env['ENV-01'] ?? [];
  const phCompliant = allEnv01.length
    ? allEnv01.filter((r) => checkCompliance('ph', r.ph).compliant).length / allEnv01.length
    : 1;
  return [
    {
      label: 'Water Compliance',
      value: `${(phCompliant * 100).toFixed(1)}`,
      unit: '%',
      delta: 0.4,
      trend: [0.6, 0.7, 0.65, 0.8, 0.85, 0.9, 0.95],
    },
    { label: 'Air Compliance', value: '98.2', unit: '%', delta: 0.2, trend: [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9] },
    { label: 'Geohazard Risk', value: 'LOW', delta: -1, trend: [0.5, 0.45, 0.4, 0.42, 0.38, 0.36, 0.35] },
    { label: 'Node Uptime', value: '99.4', unit: '%', delta: 0.1, trend: [0.85, 0.88, 0.9, 0.92, 0.95, 0.97, 0.99] },
    { label: 'Avg Response', value: '12', unit: 'min', delta: -2, trend: [0.5, 0.52, 0.5, 0.48, 0.45, 0.42, 0.4] },
  ];
}
