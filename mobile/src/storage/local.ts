/**
 * Lightweight local-first storage shared across all ASM features.
 *
 * Writes go to AsyncStorage keyed by a namespaced string; reads
 * decode defensively (bad JSON → empty, not a crash). Every record
 * carries a client-generated id + createdAt so a later backend-sync
 * pass can diff.
 *
 * Everything stays on the device until the user explicitly submits.
 * This is deliberate: the ASM user base rightly distrusts tools that
 * exfiltrate their location, production, or identity without consent.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';

const PREFIX = 'geosentinel:';

export async function readAll<T>(key: string): Promise<T[]> {
  try {
    const raw = await AsyncStorage.getItem(PREFIX + key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

export async function writeAll<T>(key: string, rows: T[]): Promise<void> {
  await AsyncStorage.setItem(PREFIX + key, JSON.stringify(rows));
}

export async function append<T>(key: string, row: T): Promise<T[]> {
  const existing = await readAll<T>(key);
  const next = [...existing, row];
  await writeAll(key, next);
  return next;
}

export async function clear(key: string): Promise<void> {
  await AsyncStorage.removeItem(PREFIX + key);
}

/** Random id suitable for a client-generated record. */
export function uid(prefix = 'rec'): string {
  const rand = Crypto.getRandomBytes(8);
  const hex = Array.from(rand)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `${prefix}-${Date.now().toString(36)}-${hex}`;
}

/**
 * Content hash of a record's canonical payload — used as the receipt
 * "integrity hash" today, and as the payload the backend's Ed25519
 * endpoint will sign at sync time. SHA-256 via expo-crypto's native
 * implementation (no WebCrypto polyfill needed).
 */
export async function sha256Json(obj: unknown): Promise<string> {
  const canonical = JSON.stringify(obj, Object.keys(obj as object).sort());
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, canonical);
}
