# Phase 2.2 — Operational maturity

Goal: make the system diagnosable, scalable, and recoverable under real load.

Status: **core items landed.** Tracing + Sentry + multi-arch images deferred
to a follow-up slice. Commits: `e7761b0` (WS + health + CORS + Celery + JSON
logs), `370db59` (Prometheus metrics), `82e8736` (CI + ruff + restore
runbook).

## Checklist

### Observability
- [ ] OpenTelemetry tracing: FastAPI middleware + SQLAlchemy instrumentation
      + Celery signals. *(Deferred — needs OTLP collector in infra.)*
- [ ] Export traces to an OTLP collector (Tempo / Jaeger). *(Deferred.)*
- [x] Prometheus metrics endpoint `/metrics` — stdlib collector, text
      exposition format. Edge nginx blocks public access.
- [ ] Celery metrics via `celery-prometheus-exporter`. *(Follow-up.)*
- [x] Custom counters:
      `gs_alerts_emitted_total{severity,type}`,
      `gs_ingest_rows_total{kind}`,
      `gs_ai_inference_seconds{model}` (histogram ready, wiring TBD),
      `gs_ws_subscribers{site_id}`,
      `gs_login_failures_total`.
- [ ] Grafana dashboards committed under `infra/grafana/`. *(Follow-up —
      dashboards best authored against a real scrape.)*

### Health checks
- [x] `/health/live` — process up.
- [x] `/health/ready` — checks Postgres + Redis with 2 s timeouts, 503 on
      failure. Influx treated as optional (fallback covers it).
- [x] Compose `healthcheck` stanza on the backend service.

### Logging
- [x] Structured JSON logs via stdlib `JsonFormatter` — one JSON record per
      log line, extras preserved, non-serialisable values coerced to repr.
- [x] `RequestIdMiddleware` sets a `request_id` contextvar consumed by the
      formatter; every request/response pair carries an `X-Request-Id` header.
- [ ] Frontend Sentry (or equivalent) with source-map upload in CI.
      *(Follow-up — needs a Sentry project.)*

### Celery topology
- [x] Dedicated `celery-beat` service in `docker-compose.prod.yml` (worker
      no longer runs `--beat`).
- [x] Two workers: `celery-worker-default` (queue=default) and
      `celery-worker-ml` (queue=ml). AI tasks routed to the ml queue.
- [x] `task_time_limit` + `soft_time_limit` + `task_acks_late` +
      `task_reject_on_worker_lost` configured globally.
- [x] Per-task `autoretry_for=(Exception,)` with `retry_backoff` +
      `retry_jitter` for the two AI tasks.
- [ ] `celery-redbeat` for scheduler HA if >1 beat instance. *(Single-beat
      is fine for the pilot; revisit at fleet scale.)*

### WebSocket scale
- [x] `asyncio.gather(...)` with per-send 2 s timeout in `hub.broadcast`.
- [x] Subscriber gauge (`gs_ws_subscribers{site_id}`) updated on
      connect/disconnect.
- [x] Slow + failing clients pruned from the subscription set.
- [ ] Idle-socket pruning (no-pong > 90 s → close). *(Follow-up — needs a
      heartbeat protocol change.)*
- [ ] Move pub/sub to Redis for multi-replica backend. *(Follow-up.)*

### Backups + DR
- [x] Restore runbook published: `docs/ops/restore.md` with RPO/RTO table,
      Postgres/Influx/model-artifact restore commands, audit-chain break
      triage, and DR drill checklist.
- [ ] Nightly `pg_dump` → S3 (Object Lock) — cron/CD wiring in the
      pilot-specific infra repo.
- [ ] Influx `backup` snapshot nightly. *(Same.)*
- [ ] Model dir `rsync` to object storage, versioned. *(Same.)*

### Deployment
- [x] GitHub Actions CI: ruff lint + pytest on backend (py3.11 + py3.12)
      against real Postgres + Redis service containers; frontend
      typecheck + lint + build on Node 20; docker build smoke for both
      images on PRs and main.
- [ ] SBOM (`syft`) and image scan (`grype`) in CI. *(Follow-up.)*
- [ ] Multi-arch backend image (`linux/amd64,linux/arm64`). *(Follow-up.)*
- [ ] Release automation: tag → image push → compose file bump PR.
      *(Follow-up.)*
- [ ] Staging environment mirrors prod (`docker-compose.staging.yml`).
      *(Follow-up.)*

### Acceptance

- [ ] 99.5 % uptime over a 2-week soak.
- [ ] p95 `/api/v1/sensors/ingest` < 150 ms at 10 req/s.
- [ ] Grafana screenshot pack committed.
- [ ] On-call runbook published (restore.md is the first chapter).
