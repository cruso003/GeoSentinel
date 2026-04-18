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

1. Strict prod config validator ✅ `5603e77`
2. CSV formula-injection escape ✅ `5603e77`
3. Edge nginx TLS + security headers ✅ `5603e77`
4. Rate limit login + ingest ✅ `5603e77`
5. JSON scalers (drop pickle) ✅ `9e35b1f`
6. WebSocket JWT auth ✅ `cc09340`
7. Per-gateway credentials + node scoping ✅ `816e664`
8. Refresh-token revocation + `/auth/logout` ✅ `2ab66a1`
9. Audit log hash chain ✅ `cb1946c`
10. `HttpOnly` refresh cookie + CSRF double-submit ✅ `c8aeeeb` (SPA migration follows)

Phase 2.2 (operational maturity) landed across
`e7761b0`, `370db59`, `82e8736`, `2d1aea9`.

Phase 2.3 (notifications + RBAC) backend landed in `e1e6dee`:
subscriptions schema, `require_site_role`, escalation sweep, local-language
templates, profile + subscription + test-alert + admin-subscribers
endpoints. UI slice (profile page, admin subscribers table, test-alert
button) is the remaining follow-up.

Mark items in each phase doc with `[x]` when they land; reference the commit
in the checklist so the doc doubles as a traceability record.
