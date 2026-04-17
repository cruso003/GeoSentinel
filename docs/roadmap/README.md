# GeoSentinel Roadmap

Living index for post-Phase-2 work, derived from the Phase-2 review
(`docs/reviews/phase-2-review.md`).

Phases are ordered by deploy-readiness dependency:

1. [**Phase 2.1 — Security hardening**](./phase-2.1-security-hardening.md) — prerequisite for any customer-facing deploy.
2. [**Phase 2.2 — Operational maturity**](./phase-2.2-operational-maturity.md) — observability, scale, backups.
3. [**Phase 2.3 — Notifications + RBAC**](./phase-2.3-notifications-rbac.md) — finish the alert story and scope data per user.
4. [**Phase 2.4 — MLOps**](./phase-2.4-mlops.md) — real labels, eval harness, model drift.
5. [**Phase 3 — Product depth**](./phase-3-product-depth.md) — second-site features, community SMS, offline PWA.

Cross-cutting:
- [**Functional gaps**](./functional-gaps.md) — items that are wired-but-incomplete.
- [**Security findings**](../security-findings.md) — full catalog with severity.

## Execution order (practical)

Within 2.1, start with changes that are isolated and low-risk, leaving the
auth-cookie migration for last because it touches both stacks:

1. Strict prod config validator
2. CSV formula-injection escape
3. Edge nginx TLS + security headers
4. Rate limit login + ingest
5. JSON scalers (drop pickle)
6. WebSocket JWT auth
7. Per-gateway credentials + node scoping
8. Refresh-token revocation + `/auth/logout`
9. Audit log hash chain
10. Move access token to memory + `HttpOnly` refresh cookie + CSRF

Mark items in each phase doc with `[x]` when they land; reference the commit
in the checklist so the doc doubles as a traceability record.
