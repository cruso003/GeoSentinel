# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

GeoSentinel is the Phase-1 implementation of `GeoSentinel_Dashboard_Spec_v1.0.docx`: an AI-powered environmental compliance and geohazard intelligence platform for African iron-ore mining. Pilot site is Tokadeh (Nimba County, Liberia). The repo is a monorepo; all three top-level apps are meant to run together via `docker-compose.dev.yml`.

```
frontend/   React 18 + TS + Vite + Tailwind + Three.js + Leaflet dashboard
backend/    FastAPI + SQLAlchemy 2 async + Alembic + Celery + MQTT + InfluxDB
ai/         EnviroGuard (LSTM+Attention) + SlopeWatch (PINN + Mohr-Coulomb)
infra/      mosquitto broker config
```

## Commands

Whole stack (recommended for feature work):
```
docker compose -f docker-compose.dev.yml up --build
```
Dashboard → http://localhost:5173, API → http://localhost:8000/api/v1, docs → http://localhost:8000/docs.

Backend only:
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.core.seed         # Tokadeh site + 5 nodes + 2 slopes + 3 users
uvicorn app.main:app --reload
pytest                          # or pytest tests/test_health.py -k mohr_coulomb
```

Frontend only:
```
cd frontend
npm install
npm run dev        # Vite dev server on :5173 (proxies /api and /ws to :8000)
npm run build      # tsc -b && vite build
npm run typecheck  # tsc -b --noEmit
npm run lint
```

Celery worker+beat (separate from uvicorn):
```
cd backend && celery -A app.tasks.celery_app worker --beat -l info
```

Seed users (password `geosentinel`): `admin@geosentinel.dev` (esg_admin) · `operator@geosentinel.dev` (operator) · `community@geosentinel.dev` (community).

## Architecture

### Frontend data flow

The dashboard has two modes switched by `useUIStore.mockMode`:

- **Mock mode (default)** — `src/mock/engine.ts` ticks every 5 s (1 s wall = 12 s sim), generating deterministic env/geo readings via mulberry32 seeded by `(node_id, timestamp)`. The active scenario in `uiStore` (`normal` · `rainfall_event` · `tailings_seepage` · `slope_warning` · `node_offline`) overlays scenario-specific shifts onto baselines. The same engine runs both `genEnviroGuard`/`genSlopeWatch` AI stubs every 3 ticks so predictions track the scenario rather than drift independently.
- **Live mode** — Phase 2 will swap `useDataEngine` to hydrate from `/api/v1/*` + subscribe to `/ws/{site_id}`.

**Stores (Zustand, all in `src/store/`)**: `sensorStore` (latest + 1440-point history), `alertStore` (dedup within 60 s per node+param+severity, recompute critical/evacuation flags), `aiStore`, `uiStore` (persisted — tab, scenario, demo flags), `authStore` (persisted session, `loginAsMock(role)`).

**Routing (`App.tsx`)** role-guards: `community` → `/community/:siteId`, `operator`+`esg_admin` → `/operations/*`, `esg_admin` → `/esg/*`. `useDemoParams` reads `?demo=true|walkthrough&scenario=...` from URL, auto-logs in a mock operator, and triggers `WalkthroughController` to auto-navigate through 9 narrated steps (`src/demo/walkthrough.ts`).

**Three.js twin** (`src/components/twin/`) projects node lat/lng onto a procedural cone-frustum pit with 6 benches × 48 segments; exclusion cylinders render for CRITICAL/EVACUATION slopes.

### Backend service wiring

`app/main.py` `lifespan` connects `influx` (falls back to in-memory ring buffer per `(measurement, node_id)` keyed `deque`(maxlen=20 000) if InfluxDB unreachable) and starts `mqtt_client` (no-op if `paho-mqtt` or broker unavailable). WebSocket endpoint `/ws/{site_id}` registers the socket with `hub` (`app/services/ws_hub.py`) which broadcasts 4 message types: `SENSOR_UPDATE`, `ALERT_NEW`, `ALERT_ACKNOWLEDGED`, `AI_PREDICTION`. `NODE_STATUS` is in the schema but not yet emitted (needs a `last_seen` sweep from MQTT + alert integration — see `docs/roadmap/functional-gaps.md`).

All v1 routes live under `app/api/v1/` and are aggregated by `app/api/v1/__init__.py` → `api_router` mounted at `/api/v1`. `require_roles("operator", "esg_admin")` is the standard guard; the community dashboard is intentionally unauthenticated (Spec §5.2.7). The gateway ingest endpoint (`POST /sensors/ingest`) is authenticated with a static `X-Gateway-API-Key` header (`settings.mqtt_gateway_api_key`).

### AI inference split

`backend/app/services/enviroguard.py` + `slopewatch.py` return Pydantic predictions. Phase 1 they emit deterministic values derived from time-of-day (EnviroGuard) or a constant baseline (SlopeWatch) — this is intentional: the *frontend* mock engine drives scenarios, and the backend only takes over when real InfluxDB data is present.

`ai/enviroguard/model.py` + `ai/slopewatch/model.py` define the Keras architectures that Phase 2 will train. `ai/slopewatch/physics/mohr_coulomb.py` implements Bishop's simplified FoS iteratively and is wired as a physics-constrained loss term into the SlopeWatch PINN.

### Celery schedule

`app/tasks/celery_app.py` beats three jobs: EnviroGuard every 15 min, SlopeWatch every 5 min, InSAR weekly (Sunday 03:00 UTC). Each task opens its own `SessionLocal()` — Celery workers are sync, the task bodies run the async service functions via `asyncio.run(...)`.

### Scenario contract

Scenario parameters must stay consistent across three places or the demo desynchronizes:
1. `frontend/src/mock/scenarios.ts` — registry.
2. `frontend/src/mock/envMockData.ts` / `geoMockData.ts` — physical overlays (e.g. `tailings_seepage` lerps conductivity 220→470 µS/cm at ENV-02 via `smooth(frac)`).
3. `frontend/src/mock/aiMockData.ts` — matching AI probabilities (e.g. `conductivity_exceedance_24h` lerps 0.05→0.88).

When adding a scenario, mirror it in all three, and wire a narration step in `src/demo/walkthrough.ts` if it should appear in the guided tour.

### IFC thresholds

`frontend/src/utils/ifc-thresholds.ts` is the single source of compliance truth for the frontend (pH 6–9, turbidity ≤5 NTU, conductivity ≤500 µS/cm, PM2.5 ≤25 µg/m³, etc.). `checkCompliance(param, value)` returns `{compliant, near_limit, exceeded}` using a 20% near-limit band. Backend alert generation (Phase 2) must use the same values; do not diverge.

### Path aliases

Frontend: `@/*` → `frontend/src/*` (see `tsconfig.json` + `vite.config.ts`). Backend imports are always `app.*` — Alembic's `env.py` sets `prepend_sys_path = .` so migrations import model metadata.

## Spec

`GeoSentinel_Dashboard_Spec_v1.0.docx` at the repo root is authoritative. When in doubt about UX, API shape, or data model, section numbers referenced in source comments (§4, §5, §13, §14, §15, §16) point back to the spec.
