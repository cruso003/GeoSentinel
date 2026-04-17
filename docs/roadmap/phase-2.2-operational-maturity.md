# Phase 2.2 — Operational maturity

Goal: make the system diagnosable, scalable, and recoverable under real load.

## Checklist

### Observability
- [ ] OpenTelemetry tracing: FastAPI middleware + SQLAlchemy instrumentation
      + Celery signals.
- [ ] Export traces to an OTLP collector (Tempo / Jaeger).
- [ ] Prometheus metrics endpoint `/metrics` (`prometheus-fastapi-instrumentator`).
- [ ] Celery metrics via `celery-prometheus-exporter`.
- [ ] Custom counters: `gs_alerts_emitted_total{severity,type}`,
      `gs_ingest_rows_total{kind}`, `gs_ai_inference_seconds{model}`,
      `gs_ws_subscribers{site_id}`.
- [ ] Grafana dashboards committed under `infra/grafana/`.

### Health checks
- [ ] `/health/live` — process up.
- [ ] `/health/ready` — checks Postgres, Redis, Influx, MQTT (short timeouts).
- [ ] Compose `healthcheck` stanzas on backend + edge + celery.

### Logging
- [ ] Switch to structured JSON (`structlog` or stdlib with
      `pythonjsonlogger`).
- [ ] Inject `trace_id` / `span_id` / `user_id` / `site_id` into every record.
- [ ] Frontend: Sentry (or equivalent) with source-map upload in CI.

### Celery topology
- [ ] Dedicated `beat` service (remove `--beat` from worker).
- [ ] `celery-redbeat` for scheduler HA if >1 beat instance.
- [ ] Two workers: `queue=default` and `queue=ml` (AI tasks slow).
- [ ] Task timeouts + retries with exponential backoff.

### WebSocket scale
- [ ] `asyncio.gather(*sends, return_exceptions=True)` with per-send 2 s
      timeout in `hub.broadcast`.
- [ ] Metrics per site + per client send-latency histogram.
- [ ] Idle-socket pruning (no-pong > 90 s → close).
- [ ] Optional: move pub/sub to Redis so multi-replica backend can share state.

### Backups + DR
- [ ] Nightly `pg_dump` → S3 (Object Lock).
- [ ] Influx `backup` snapshot nightly.
- [ ] Model dir `rsync` to object storage, versioned.
- [ ] Documented restore runbook in `docs/ops/restore.md`.
- [ ] Quarterly DR drill checklist.

### Deployment
- [ ] GitHub Actions CI: lint, typecheck, pytest, playwright (smoke),
      docker build, SBOM (`syft`), image scan (`grype`).
- [ ] Multi-arch backend image (`linux/amd64,linux/arm64`).
- [ ] Release automation: tag → image push → compose file bump PR.
- [ ] Staging environment mirrors prod (`docker-compose.staging.yml`).

### Acceptance

- [ ] 99.5 % uptime over a 2-week soak.
- [ ] p95 `/api/v1/sensors/ingest` < 150 ms at 10 req/s.
- [ ] Grafana screenshot pack committed.
- [ ] On-call runbook published.
