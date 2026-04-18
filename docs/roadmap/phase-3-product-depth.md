# Phase 3 — Product depth

Goal: move from a single-pilot demo to a multi-site, community-facing
product that is defensible in customer pitches (AngloGold, ArcelorMittal,
BHP Africa).

## Checklist

### Multi-site
- [ ] Sites switcher in the global nav; URL pattern `/sites/:siteId/...`.
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
- [ ] Phase 2 produced manifests; Phase 3 ingests BEAM-DIMAP pixels per
      slope AOI into Influx as `insar_displacement_mm` time series.
- [ ] UI chart: cumulative displacement (mm) per slope, with a velocity
      (mm/yr) badge.
- [ ] Feed `insar_factor` in `SlopeWatchPrediction` from this series (see
      review — currently unused).

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
