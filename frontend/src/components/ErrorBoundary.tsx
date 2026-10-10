import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Last-resort render-crash catcher.
 *
 * The brutal review flagged that a single render error anywhere in the
 * tree would blank the dashboard — WebGL failure in the Three.js twin,
 * a null-field surprise in a chart, an API-mapped undefined.  Without
 * an ErrorBoundary the operator sees a white screen with no reset path.
 *
 * This component catches, logs, and offers Reload / Reset-state buttons
 * so a 3am alert never becomes "the dashboard is dead".  It wraps the
 * root in main.tsx; nested boundaries can be added later per-view if a
 * surface's failure shouldn't take down neighbours.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('[GeoSentinel] uncaught render error', error, info.componentStack);
  }

  private reload = () => {
    window.location.reload();
  };

  private resetAndReload = () => {
    try {
      window.localStorage.clear();
      window.sessionStorage.clear();
    } catch {
      /* storage can be unavailable in private mode; reload anyway */
    }
    window.location.href = '/';
  };

  render() {
    if (!this.state.error) return this.props.children;

    const msg = this.state.error.message || 'Unknown error';
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4 text-slate-900">
        <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow">
          <h1 className="text-lg font-semibold text-red-700">
            GeoSentinel ran into an unexpected error
          </h1>
          <p className="mt-2 text-sm text-slate-700">
            The dashboard surface failed to render. The underlying monitoring and
            alerting services on the backend are not affected — this is a UI-only
            fault. Reload to recover; if the problem repeats, reset local state
            and sign in again.
          </p>
          <pre className="mt-3 max-h-40 overflow-auto rounded-md bg-slate-100 p-2 text-[11px] text-slate-700">
            {msg}
          </pre>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={this.reload}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
            >
              Reload
            </button>
            <button
              type="button"
              onClick={this.resetAndReload}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-500"
            >
              Reset local state &amp; reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
