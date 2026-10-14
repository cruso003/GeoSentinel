# GeoSentinel

**Offline-first digital tools for Liberia's artisanal and small-scale miners, their cooperatives, and the communities around them — backed by a production-grade compliance platform.**

Submitted to the UNDP timbuktoo Pan-African MineTech Pre-Incubation Programme (October 2026) under the Process Innovation (ASM) track, Challenge 2 — Informal Mining (ASM). Host: University of Liberia MineTech UniPod, Fendall campus.

---

## What it is

Three screens on a cheap Android, no login, no data plan required:

- **Where can I mine?** — GPS + bundled Copernicus GLO-30 hillshade + MME licence overlay returns an immediate `GREEN` / `YELLOW` / `RED` verdict at the current location.
- **Cooperative receipts** — register a cooperative once, then record miner-to-dealer sales (grams, karat, buyer, price). Each receipt gets a local SHA-256 integrity hash; the backend issues an Ed25519-signed PDF when the device next sees data.
- **Report a concern** — any community member can file a water / forest / safety / mercury concern with a photo, GPS pin, and short note. Routed to EPA / FDA on upload inside a signed envelope.

Behind the mobile app runs a production-grade compliance platform (FastAPI + PostgreSQL + Celery + MQTT + InfluxDB) with trained ONNX classifiers, a hash-chained tamper-evident audit log, Ed25519 report envelopes, and a 3D Mount Nimba terrain twin built from real Copernicus GLO-30 digital elevation data. The platform drives a dormant corporate operator dashboard which activates once GISTM enforcement reaches Liberia.

See `mobile/screenshots/` (Android, 16 shots) and `docs/screenshots/` (web dashboard, 9 shots) for how it looks today.

---

## Why

Liberia has approximately 100,000 artisanal and small-scale gold miners, supporting ~1.6 million dependants. The MME cadastre maps only 18 of the ~2,500 active and applicant Class-C licences. Under-reported gold is estimated to cost Liberia hundreds of millions of dollars a year. Nearly half of the country's forest overlaps active or applicant mining licences, and 53 of 64 community forests sit on top of licensed areas.

The MME Online Repository launched in December 2025. Nobody has yet built the mobile layer on top of it. GeoSentinel goes first.

---

## Current status (honest)

- **TRL 5.** Working prototype across all four surfaces (mobile, backend, frontend, AI).
- **Zero deployed customers.** First pilot cooperative onboarding is the goal of the Oct–Dec 2026 pre-incubation window.
- **Trained ML in-tree.** `ai/enviroguard/artifacts/` ships seven ONNX gradient-boosting classifiers (~82 KB each). A deterministic surrogate is gated behind an explicit feature flag that is forbidden in production. See `ai/enviroguard/README.md` for the training protocol and metrics.
- **Real geospatial data.** The 3D twin and the mobile hillshade are built from Copernicus GLO-30 DEM (ESA, free-and-open, cited).
- **No formal partnerships yet.** Conversations with MME, EPA, FDA, and cooperatives are pre-incubation goals, not current state.

---

## Layout

```
mobile/          React Native + Expo Router — the ASM-primary Android app
                 (3 screens: where-can-i-mine, receipts, report-concern)
backend/         FastAPI + SQLAlchemy 2 async + Alembic + Celery + MQTT + InfluxDB
                 Ed25519 envelope signing, hash-chained audit log, ONNX inference
frontend/        React 18 + TS + Vite + Tailwind + Three.js — operator dashboard
                 (dormant until GISTM / corporate conversation)
ai/              EnviroGuard (ONNX gradient-boosting classifiers, trained)
                 SlopeWatch (Bishop's Mohr-Coulomb FoS kernel + training scaffold)
docs/            Architecture, roadmap, security findings, screenshots
infra/           mosquitto broker config
```

---

## Quick start — whole stack (Docker)

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Dashboard: http://localhost:5173
- API: http://localhost:8000/api/v1
- API docs: http://localhost:8000/docs

Seed users (password `geosentinel`):

- `admin@geosentinel.dev` — ESG admin
- `operator@geosentinel.dev` — control-room operator
- `community@geosentinel.dev` — public community portal

---

## Quick start — mobile app

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with Expo Go on any Android with GPS. The app bundles its licence dataset and hillshade — no backend required to try the three screens.

---

## Quick start — backend only (no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.core.seed
uvicorn app.main:app --reload
```

InfluxDB and MQTT are optional — the backend transparently falls back to an in-memory ring buffer so you can run without either.

---

## Quick start — frontend only

```bash
cd frontend
npm install
npm run dev
```

---

## Demo mode

The dashboard ships with a deterministic mock engine so you can exercise the whole spec without provisioning any IoT hardware:

- `?demo=true` — mock data on, operator session auto-created
- `?demo=true&scenario=rainfall_event` — drive a specific scenario
- `?demo=walkthrough` — auto-navigating 3–4 minute guided tour

Scenarios: `normal`, `rainfall_event`, `tailings_seepage`, `slope_warning`, `node_offline`.

---

## Tests

```bash
cd backend && pytest
cd frontend && npm run typecheck && npm run lint
```

Backend parity test enforces that the frontend's IFC compliance thresholds match the backend's at the byte level (`backend/tests/test_thresholds_parity.py`). The audit chain concurrency invariant is pinned in `backend/tests/test_audit_concurrency.py`. End-to-end ONNX inference is covered in `backend/tests/test_enviroguard_baseline.py`.

---

## Documentation

- `GeoSentinel_Dashboard_Spec_v1.0.docx` — authoritative spec (section numbers referenced throughout the codebase).
- `CLAUDE.md` — architecture map for new contributors (data flow, service wiring, scenario contract, path aliases).
- `docs/roadmap/` — known functional gaps and next milestones.
- `docs/security-findings.md` — security review record.
- `ai/enviroguard/README.md` — model card for the trained ONNX classifiers (features, training set, metrics, promotion gate).

---

## Roadmap

- **Phase 1 (shipped).** ASM mobile app (3 screens), production-grade backend with trained ONNX inference + Ed25519 signing + hash-chained audit, operator dashboard + 3D Mount Nimba terrain twin, deterministic demo mode.
- **Phase 2 (pre-incubation goal, Oct – Dec 2026).** First cooperative onboarded in the Nimba corridor, 100 signed receipts, 20 community concern reports, EPA liaison conversation initiated, MME Online Repository ingest contract agreed.
- **Phase 3 (post-programme).** Fifty cooperatives, pilot MOU with MME on cadastre data exchange, corporate operator activation on the dormant dashboard layer as GISTM enforcement reaches Liberia.

---

## Team

Four Liberian nationals, multidisciplinary, cross-institutional:

- **Tedmas SY Dahn** — Team Lead · Civil engineering · International University of East Africa (graduating Nov 2026)
- **Joan Adey Williams** — Environmental engineering, first class · International University of East Africa (Nov 2025)
- **Cindy Tetama Johnson** — Computer science, final year · Cavendish University Uganda
- **Geitodyu Henrique Crusoe** — Civil & software engineering, 2nd class honours upper division · International University of East Africa (Nov 2025)

Two team members (Joan, Henrique) are based in Liberia today; two (Tedmas, Cindy) return within the Oct – Dec 2026 programme window.

---

## License

See `LICENSE`. All third-party components are open-source and compatibility-checked (FastAPI MIT, PostgreSQL License, React Native MIT, Copernicus GLO-30 DEM free-and-open with attribution, MME licence polygon data public).
