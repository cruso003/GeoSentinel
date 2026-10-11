import { useState } from 'react';
import { BellRing } from 'lucide-react';
import { confirmCommunity, subscribeCommunity } from '@/api/community';
import { ApiError } from '@/api/client';
import { clsx } from '@/utils/clsx';

type Step = 'form' | 'confirm' | 'done';

interface Props {
  siteId: string;
}

const E164_RE = /^\+\d{8,15}$/;

export function OptInCard({ siteId }: Props) {
  const [step, setStep] = useState<Step>('form');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [debugCode, setDebugCode] = useState<string | null>(null);

  const phoneValid = E164_RE.test(phone);
  const codeValid = /^\d{6}$/.test(code);

  async function onSubscribe(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!phoneValid) {
      setError('Enter your phone in international format, e.g. +231881234567.');
      return;
    }
    setLoading(true);
    try {
      const res = await subscribeCommunity({
        phone_number: phone,
        site_id: siteId,
      });
      setExpiresAt(res.expires_at);
      setDebugCode(res.debug_code);
      setStep('confirm');
    } catch (err) {
      setError(messageFor(err, 'Could not send the code. Please try again.'));
    } finally {
      setLoading(false);
    }
  }

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!codeValid) {
      setError('Enter the 6-digit code from your SMS.');
      return;
    }
    setLoading(true);
    try {
      await confirmCommunity({ phone_number: phone, site_id: siteId, code });
      setStep('done');
    } catch (err) {
      setError(messageFor(err, 'Incorrect or expired code. Try again or request a new one.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-emerald-600 text-white">
          <BellRing className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-900">Get alerts by SMS</h3>
          <p className="mt-0.5 text-xs text-slate-600">
            We will text you only when drinking water, air quality, or slopes reach a level
            that needs action. Standard carrier rates may apply.
          </p>

          {step === 'form' && (
            <form className="mt-3 space-y-2" onSubmit={onSubscribe}>
              <label className="block text-xs font-medium text-slate-700">
                Phone number
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.trim())}
                  placeholder="+231881234567"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  required
                />
              </label>
              <button
                type="submit"
                disabled={loading || !phoneValid}
                className={clsx(
                  'mt-1 inline-flex items-center justify-center rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition',
                  'disabled:cursor-not-allowed disabled:opacity-60 hover:bg-emerald-700',
                )}
              >
                {loading ? 'Sending…' : 'Send me a code'}
              </button>
            </form>
          )}

          {step === 'confirm' && (
            <form className="mt-3 space-y-2" onSubmit={onConfirm}>
              <p className="text-xs text-slate-700">
                We sent a 6-digit code to <strong>{phone}</strong>. Enter it below before{' '}
                {expiresAt ? new Date(expiresAt).toLocaleTimeString() : 'the code expires'}.
              </p>
              {debugCode && (
                <p className="rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-900 ring-1 ring-amber-200">
                  Dev mode: SMS provider not configured — your code is{' '}
                  <strong className="font-mono">{debugCode}</strong>.
                </p>
              )}
              <label className="block text-xs font-medium text-slate-700">
                Confirmation code
                <input
                  inputMode="numeric"
                  pattern="\d{6}"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="123456"
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 font-mono text-sm tracking-widest focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  required
                />
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={loading || !codeValid}
                  className={clsx(
                    'inline-flex items-center justify-center rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition',
                    'disabled:cursor-not-allowed disabled:opacity-60 hover:bg-emerald-700',
                  )}
                >
                  {loading ? 'Confirming…' : 'Confirm'}
                </button>
                <button
                  type="button"
                  onClick={() => { setStep('form'); setCode(''); setError(null); }}
                  className="text-xs font-semibold text-slate-600 underline"
                >
                  Use a different number
                </button>
              </div>
            </form>
          )}

          {step === 'done' && (
            <div className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-900 ring-1 ring-emerald-200">
              You are subscribed. We will only SMS <strong>{phone}</strong> for CRITICAL
              or EVACUATION alerts that affect this area. Reply STOP to any message to
              opt out.
            </div>
          )}

          {error && (
            <p className="mt-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-800 ring-1 ring-red-200">
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function messageFor(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return 'Too many attempts. Please wait a few minutes.';
    // The API returns `{"detail": "..."}` — parse it if we can.
    try {
      const parsed = JSON.parse(err.message);
      if (parsed && typeof parsed.detail === 'string') return parsed.detail;
    } catch {
      /* body was not JSON */
    }
    return err.message || fallback;
  }
  return fallback;
}
