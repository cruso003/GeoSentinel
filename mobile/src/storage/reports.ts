import { append, readAll, sha256Json, uid } from './local';

export type ConcernKind = 'water' | 'forest' | 'safety' | 'mercury' | 'other';

export interface ConcernReport {
  id: string;
  kind: ConcernKind;
  description: string;
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
  photoUri: string | null; // local file:// URI; backend sync uploads later
  reporterName?: string; // optional — anonymous by default
  createdAt: string;
  integrityHash: string;
  syncStatus: 'queued' | 'sent' | 'failed';
}

const REPORTS_KEY = 'reports.ledger';

export const CONCERN_LABELS: Record<ConcernKind, string> = {
  water: 'Water quality',
  forest: 'Forest / deforestation',
  safety: 'Mining safety',
  mercury: 'Mercury or chemicals',
  other: 'Other concern',
};

export const CONCERN_COLORS: Record<ConcernKind, string> = {
  water: '#22D3EE',
  forest: '#2BB07A',
  safety: '#F5B041',
  mercury: '#EF4444',
  other: '#8FA2BA',
};

export async function listReports(): Promise<ConcernReport[]> {
  const rows = await readAll<ConcernReport>(REPORTS_KEY);
  return rows.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function recordReport(input: {
  kind: ConcernKind;
  description: string;
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
  photoUri: string | null;
  reporterName?: string;
}): Promise<ConcernReport> {
  const base = {
    kind: input.kind,
    description: input.description.trim(),
    latitude: input.latitude,
    longitude: input.longitude,
    accuracyMeters: input.accuracyMeters,
    photoUri: input.photoUri,
    reporterName: input.reporterName?.trim() || undefined,
    createdAt: new Date().toISOString(),
  };
  const integrityHash = await sha256Json(base);
  const report: ConcernReport = {
    ...base,
    id: uid('rpt'),
    integrityHash,
    syncStatus: 'queued',
  };
  await append(REPORTS_KEY, report);
  return report;
}
