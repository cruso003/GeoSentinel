# Phase 3 — Product depth

Goal: move from a single-pilot demo to a multi-site, community-facing
product that is defensible in customer pitches (AngloGold, ArcelorMittal,
BHP Africa).

## Checklist

### Multi-site
- [x] Sites switcher in the global nav. `useSiteStore` loads `/me/sites`
      on mount (auth-gated) or falls back to `MOCK_SITE` in mock mode; the
      Sidebar `SiteSwitcher` is wired to `uiStore.activeSiteId`, which
      `useDataEngine` consumes to hydrate alerts/AI + subscribe the
      WebSocket to the right site. Switching sites in live mode clears the
      sensor + alert stores so old readings don't bleed through. The
      `HomeRedirect` and `ComplianceTab` report panel now resolve the
      active siteId instead of a hardcoded tokadeh-pilot literal. URL
      pattern `/sites/:siteId/...` is deferred — the store-backed approach
      keeps the current flat routes working while still being per-site.
- [ ] Org-level dashboard aggregating KPIs across sites.
- [ ] Billing / tenancy primitives if sold as SaaS.

### Community SMS
- [ ] Opt-in signup with phone confirmation (Twilio Verify).
- [ ] Local-language templates (Liberian English, Mano, Gio).
- [ ] Daily bulletin + CRITICAL pushes.
- [ ] Quarterly community meeting export (attendance, concerns, responses).

### Offline-first operator PWA
- [ ] Service worker with Workbox; precaches app shell + last 24 h of
      telemetry and alerts.
- [ ] IndexedDB write buffer for acknowledgements; replays on reconnect.
- [ ] Conflict resolution policy (server wins on ack collisions).
- [ ] Install prompt + native-like UX.

### Physics forward simulator
- [ ] Rainfall → pore-pressure coupling (Richards' equation discretised).
- [ ] Forward-cast next-6 h pore pressure per slope; overlay in twin.
- [ ] Calibrated against Tokadeh field data.

### InSAR time series
- [x] Phase 2 produced manifests; Phase 3 ingests them into Influx as
      `insar_displacement_mm` time series. `services/insar_ingest.py`
      parses the manifest, synthesises a scene-cadence series from the
      pair mean (+ a deterministic per-slope offset so multi-slope
      sites show distinct curves), and writes one point per scene per
      slope via `influx.write_insar`. The weekly Celery task
      (`insar_processing.process_sentinel1_scene`) now calls ingest
      after `pipeline.run` so the beat actually populates the series.
      The real BEAM-DIMAP pixel sampler is flagged for a follow-up —
      current scope treats the manifest's pair-level
      `displacement_mm_mean` as the site signal.
- [x] UI chart: cumulative displacement (mm) per slope with a
      velocity (mm/yr) badge. `InsarDisplacementCard` in
      `components/charts/` is wired into GeotechnicalTab below the
      tilt/pore-pressure grid, hits `GET /sites/{site}/slopes/{slope}/insar`
      (site-role scoped), and falls back to a deterministic mock series
      in `getSlopeInsar` when the frontend is in mock mode. Badge tone
      mirrors the velocity ladder so the colour scheme is consistent
      with SlopeWatch's `insar_factor`.
- [x] `insar_factor` in `SlopeWatchPrediction` now reads
      `latest_velocity_mm_yr` and runs it through `velocity_to_factor`
      (5/10/20/50 mm/yr ladder → 0.1/0.2/0.45/0.75/1.0). When the
      Influx ring has no points for the slope yet the service falls
      back to the legacy `0.15 * score` weighting so existing demos
      still produce a bar. Coverage: `backend/tests/test_insar_ingest.py`
      (13 tests).

### IFC PDF reports
- [x] ReportLab template matching Spec §15.4. The generator now renders
      real per-parameter compliance stats pulled from the alert log, a
      capped exceedance event log (CRITICAL/EVACUATION only, newest first),
      and a geohazard summary built from SlopeWatchPrediction rows for the
      period. `ReportData` ships as a frozen dataclass so the renderer and
      stats collector can't drift.
- [x] Auto-generated from `/reports/generate` — ESG admin only — and the
      frontend ReportPanel issues the call, polls status, and downloads via
      authenticated fetch → Blob (cookies + bearer-token safe). Object
      storage is still `/tmp/geosentinel-reports` on disk; S3 upload is a
      follow-up.
- [x] SHA-256 pinned in `ComplianceReport.data_integrity_hash`; derived from
      every row the renderer consumed (stats + log + geohazard), so a
      reviewer can re-hash the source data to verify. Unit coverage:
      `backend/tests/test_report_stats.py`.
- [ ] Sign with an offline key.
- [ ] Move generation onto Celery (`ml` queue) so quarterly reports can
      include InfluxDB aggregates without blocking the request thread.

### Mobile native
- [ ] Expo/React Native app for operators (twin view, alerts, ack, camera
      for calibration snapshots).
- [ ] Push via APNs/FCM.

### Quality
- [ ] Playwright E2E covering the 9-step demo walkthrough.
- [ ] Lighthouse CI gate > 90 on dashboards.
- [ ] Backend integration tests ≥ 70 % coverage of `services/`.
- [ ] CI green before every merge to `main`.

### Research
- [ ] Whitepaper: "Physics-informed slope monitoring at Tokadeh" with real
      data, publishable before ACP or NHESS.
- [ ] Ethics review with Nimba County community liaison.

### Acceptance

- [ ] Two production sites live (Tokadeh + second customer).
- [ ] Community channel has ≥ 1 000 opted-in subscribers.
- [ ] Offline PWA survives 24-h disconnect with no data loss.
- [ ] IFC report passes a reviewer audit.
