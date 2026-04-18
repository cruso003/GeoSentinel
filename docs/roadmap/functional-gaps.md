# Functional gaps

Wired-but-incomplete items surfaced in the Phase-2 review. Most of these are
subsumed by the phase plans but listed here as the "honest truth about what
doesn't actually work yet".

## Checklist

- [ ] **Notifications recipients empty.** `NotificationService._recipients_for_site`
      returns `[]`. Email and SMS never send. → Phase 2.3.
- [ ] **IFC thresholds drift.** Same values in
      `backend/app/services/thresholds.py` and
      `frontend/src/utils/ifc-thresholds.ts`. No parity test.
  - [ ] Extract to a shared JSON file (`shared/ifc-thresholds.json`).
  - [ ] Backend loads the JSON at import time.
  - [ ] Frontend imports the JSON via Vite's JSON support.
  - [ ] CI parity test diffs the two loaders.
- [ ] **SlopeWatch factor decomposition is arithmetic.**
      `pore = 0.35 * score` etc. Either rename to "illustrative breakdown"
      or replace with SHAP. → Phase 2.4.
- [ ] **InSAR manifest has no consumer.** Pipeline writes `manifest.json`;
      nothing reads it. Needs downstream wiring into a
      `SlopeWatchPrediction.insar_factor` update. → Phase 3.
- [ ] **No `/auth/logout` endpoint.** Refresh tokens live 30 days even
      after the user hits "Sign out". → Phase 2.1 §8.
- [ ] **No per-site RBAC.** Any operator sees every site. → Phase 2.3.
- [ ] **Mock auth tokens leak to `localStorage`.** `loginAsMock` writes
      `mock-operator-token` which the real `api` client would send as
      `Bearer`. Add a guard that strips `mock-` prefixed tokens.
- [ ] **`alembic upgrade head && python -m app.core.seed`** in the dev
      compose re-seeds on every boot. Mirror of this in a prod compose
      would create demo users with the password `geosentinel`. Prod compose
      currently excludes the seed — keep it that way, document it.
- [ ] **React error boundary missing.** A single render crash blanks the
      dashboard. Add a top-level `ErrorBoundary` with reset + Sentry hook.
- [ ] **Mock→live toggle has no UI.** Only `uiStore.mockMode` via devtools.
      Add an ESG/operator settings drawer.
- [ ] **Backend tests ≈ 25 LOC.** Zero coverage of `alert_engine`,
      `notifications`, `audit`, `tflite_runtime`, InSAR pipeline. → add
      alongside the relevant phase.
- [ ] **WS hub broadcasts serially.** One slow client stalls every other
      subscriber. → Phase 2.2.
- [ ] **Celery `--beat` embedded in the worker.** Scaling workers
      duplicates schedules. → Phase 2.2.
- [ ] **Frontend bundle has no code splitting.** Three.js + Leaflet load on
      first paint for every role, including the community page.

## Nice-to-haves

- [ ] Loosen `allow_methods=["*"]` / `allow_headers=["*"]` on CORS.
- [ ] `datetime.utcnow()` → `datetime.now(timezone.utc)` audit.
- [ ] `gs_models` volume ownership — fix for non-root backend user.
