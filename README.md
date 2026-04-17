# GeoSentinel

AI-Powered Predictive Environmental Compliance & Geohazard Intelligence Platform for African Mining.

Implements `GeoSentinel_Dashboard_Spec_v1.0.docx` — a control-room dashboard, AI
inference services (EnviroGuard + SlopeWatch), a 3D digital twin, ESG compliance
reporting, and a public community portal. The Tokadeh iron-ore mine (Nimba
County, Liberia) is the Phase-1 pilot site.

## Layout

```
frontend/   React 18 + TS + Vite + Tailwind + Three.js + Leaflet
backend/    FastAPI + SQLAlchemy 2 + Alembic + Celery + MQTT + InfluxDB
ai/         EnviroGuard (LSTM+Attention) + SlopeWatch (PINN + Mohr-Coulomb)
infra/      mosquitto config
```

## Quick start (Docker)

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Dashboard:   http://localhost:5173
- API:         http://localhost:8000/api/v1
- Health:      http://localhost:8000/health
- API docs:    http://localhost:8000/docs

Seed users (password `geosentinel`):

- `admin@geosentinel.dev` — ESG admin
- `operator@geosentinel.dev` — control-room operator
- `community@geosentinel.dev` — public community portal

## Local dev (no Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.core.seed
uvicorn app.main:app --reload
```

The InfluxDB + MQTT connections are optional; the backend falls back to an
in-memory ring buffer so you can run without either.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Demo mode

The dashboard ships with a deterministic mock engine so you can exercise the
whole spec without provisioning any IoT hardware. Use URL params:

- `?demo=true` — mock data on, operator session auto-created
- `?demo=true&scenario=rainfall_event` — drive a specific scenario
- `?demo=walkthrough` — auto-navigating 3–4 min guided tour

Scenarios: `normal`, `rainfall_event`, `tailings_seepage`, `slope_warning`,
`node_offline`.

## Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Roadmap

- Phase 1 — dashboard + backend API + mock data + ESG reports (this repo).
- Phase 2 — train EnviroGuard + SlopeWatch on Tokadeh telemetry, wire real MQTT,
  InSAR processing via ESA Copernicus, TFLite on-node inference.
- Phase 3 — multi-site rollout.
