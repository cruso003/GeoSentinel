import { append, readAll, sha256Json, uid, writeAll } from './local';

export interface Cooperative {
  id: string;
  name: string;
  chairName: string;
  mineral: 'gold' | 'diamond' | 'other';
  siteNotes: string;
  createdAt: string;
}

export interface Receipt {
  id: string;
  cooperativeId: string;
  minerName: string;
  weightGrams: number;
  purityPercent: number; // 0-100
  pricePerGramUSD: number;
  totalUSD: number;
  dealerName: string;
  dealerLicenceNo?: string;
  notes?: string;
  createdAt: string;
  integrityHash: string;
  signedByBackend: boolean; // false locally; set true after a successful sync
}

const COOP_KEY = 'receipts.cooperative';
const RECEIPTS_KEY = 'receipts.ledger';

/** Current cooperative — the app only tracks one at a time (per-device). */
export async function getCooperative(): Promise<Cooperative | null> {
  const rows = await readAll<Cooperative>(COOP_KEY);
  return rows[0] ?? null;
}

export async function setCooperative(coop: Omit<Cooperative, 'id' | 'createdAt'>): Promise<Cooperative> {
  const row: Cooperative = {
    ...coop,
    id: uid('coop'),
    createdAt: new Date().toISOString(),
  };
  await writeAll(COOP_KEY, [row]);
  return row;
}

export async function clearCooperative(): Promise<void> {
  await writeAll(COOP_KEY, []);
  await writeAll(RECEIPTS_KEY, []);
}

export async function listReceipts(): Promise<Receipt[]> {
  const rows = await readAll<Receipt>(RECEIPTS_KEY);
  // newest first
  return rows.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function recordReceipt(input: {
  cooperativeId: string;
  minerName: string;
  weightGrams: number;
  purityPercent: number;
  pricePerGramUSD: number;
  dealerName: string;
  dealerLicenceNo?: string;
  notes?: string;
}): Promise<Receipt> {
  const totalUSD = Number(
    (input.weightGrams * (input.purityPercent / 100) * input.pricePerGramUSD).toFixed(2),
  );
  const base: Omit<Receipt, 'id' | 'integrityHash' | 'signedByBackend' | 'createdAt'> & {
    createdAt: string;
  } = {
    cooperativeId: input.cooperativeId,
    minerName: input.minerName.trim(),
    weightGrams: input.weightGrams,
    purityPercent: input.purityPercent,
    pricePerGramUSD: input.pricePerGramUSD,
    totalUSD,
    dealerName: input.dealerName.trim(),
    dealerLicenceNo: input.dealerLicenceNo?.trim() || undefined,
    notes: input.notes?.trim() || undefined,
    createdAt: new Date().toISOString(),
  };
  const integrityHash = await sha256Json(base);
  const receipt: Receipt = {
    ...base,
    id: uid('rcpt'),
    integrityHash,
    signedByBackend: false,
  };
  await append(RECEIPTS_KEY, receipt);
  return receipt;
}

/** Short display fingerprint for the integrity hash — enough entropy
 * for a cooperative chair to visually confirm two receipts don't collide,
 * fits on a line of a thermal-printer slip. */
export function fingerprint(hash: string): string {
  return `${hash.slice(0, 4)}:${hash.slice(4, 8)}…${hash.slice(-4)}`.toUpperCase();
}
