import { api, ApiError, BASE_URL } from './client';
import { useAuthStore } from '@/store/authStore';
import type { ComplianceReport, ReportType } from '@/types';

export interface GenerateReportRequest {
  site_id: string;
  period_start: string; // ISO 8601
  period_end: string;
  report_type: ReportType;
}

export async function generateReport(
  body: GenerateReportRequest,
): Promise<ComplianceReport> {
  return api.post('/reports/generate', body);
}

export async function getReport(reportId: string): Promise<ComplianceReport> {
  return api.get(`/reports/${reportId}`);
}

export async function listReports(): Promise<ComplianceReport[]> {
  return api.get('/reports');
}

export interface ReportSignatureBundle {
  report_id: string;
  signature_b64: string;
  pubkey_hex: string;
  pdf_sha256: string;
}

/** Fetches the detached Ed25519 signature bundle for an auditor to verify
 * the PDF offline. Backend returns 404 for unsigned/legacy reports. */
export async function getReportSignature(
  reportId: string,
): Promise<ReportSignatureBundle> {
  return api.get(`/reports/${reportId}/signature`);
}

/** Fetches the PDF with the current session's bearer token and triggers a
 * browser download. `<a href>` can't attach auth headers, so this has to go
 * through fetch → Blob → object URL. */
export async function downloadReport(report: ComplianceReport): Promise<void> {
  const session = useAuthStore.getState().session;
  const url = `${BASE_URL}/reports/${report.id}/download`;
  const res = await fetch(url, {
    headers: session ? { Authorization: `Bearer ${session.access_token}` } : {},
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || res.statusText, res.status);
  }
  const blob = await res.blob();
  const filename = `GeoSentinel_${report.report_type}_${report.period_start.slice(0, 10)}_${report.period_end.slice(0, 10)}.pdf`;
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}
