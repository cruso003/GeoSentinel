# Phase 2 review — commit `76ff179`

Branch `claude/geosentinel-dashboard-spec-x6fy6`. ~8.8 k LOC of source, 25
LOC of tests.

## Ratings

| Dimension | Rating | Notes |
|---|---|---|
| Architecture | 7/10 | Clear monorepo, right abstractions, graceful fallbacks. |
| Security | 4/10 | Prod-unsafe as-shipped. See `docs/security-findings.md`. |
| Feature coverage vs spec | 7/10 | Alerts, audit, AI, InSAR, WS live mode present; notifications plumbing incomplete. |
| AI / ML maturity | 5/10 | Trainable; physics-informed; synthetic labels; no eval/MLOps. |
| Observability / Ops | 4/10 | `/health` only; no metrics, traces, dep health, rate-limiting. |
| Testing | 2/10 | 25 LOC of tests; no integration, no E2E, no parity. |
| Documentation | 7/10 | Spec + `CLAUDE.md` + inline §refs. No runbook. |
| **Overall** | **6/10** | Solid demo / pilot-grade; not production-grade. |

## Strengths

- Graceful degradation: TFLite→Mohr-Coulomb/diurnal, ESA→synthetic, MQTT→no-op,
  aiosmtplib→stdlib.
- Physics-informed ML: SlopeWatch PINN uses Bishop's simplified FoS both as
  the gold label and as a smoothness regulariser.
- Correct invariants: 60-s alert dedup, role-guarded routes, append-only audit
  model.
- Two-mode data engine (`mockMode`) with minimal coupling.
- Spec cross-references (`§8.5`, `§13` ...) are a real asset.

## Weaknesses (summary — detail in the roadmap docs)

- Security: unauth WebSocket, shared gateway key, JWT in localStorage, no
  refresh revocation, audit log mutable, no rate limits, no TLS/CSP at the
  edge, pickle model artifacts.
- Notifications stubbed: `_recipients_for_site` returns `[]`.
- InSAR pipeline writes a manifest no one reads.
- SlopeWatch factor decomposition is arithmetic, not learned.
- IFC thresholds duplicated across frontend and backend; no parity test.
- 25 LOC of tests: critical services uncovered.
- Celery `--beat` embedded in worker prevents horizontal scale.
- No observability: no metrics, no traces, no structured logs, no readiness.

## Roadmap

See `docs/roadmap/README.md`. Phases 2.1 → 2.2 → 2.3 → 2.4 → 3.

## Bottom line

Credible Phase-2 pilot platform. Not production-grade for an operating mine
until Phase 2.1 lands. Treat this as a strong demo / funding artifact and
budget 4–6 weeks of focused 2.1–2.3 work before a real Tokadeh cutover.
