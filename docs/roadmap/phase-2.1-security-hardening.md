# Phase 2.1 — Security hardening

**Deploy gate.** Do not expose GeoSentinel to customer or gateway traffic until
items 1–5 below land.

Status: **all 10 items landed.** See commits `5603e77` (§1–4), `9e35b1f` (§5),
`cc09340` (§6), `816e664` (§7), `2ab66a1` (§8), `cb1946c` (§9), `c8aeeeb` (§10).

## Checklist

### 1. Strict production config validator ✅
- [x] Pydantic `@model_validator(mode="after")` rejects default/empty values for
      `jwt_secret_key`, `influxdb_token`, `mqtt_gateway_api_key`, and
      `allowed_origins` when `env == "production"`.
- [x] Rejects `jwt_secret_key` shorter than 32 chars.
- [x] Fails fast on boot with an aggregated error list.
- [x] Unit-tested in `backend/tests/test_config.py` (8 cases).

### 2. CSV formula-injection escape in `/audit/export.csv` ✅
- [x] `backend/app/services/csv_safe.py` escapes cells starting with `=`, `+`,
      `-`, `@`, `\t`, `\r` by prefixing `'`.
- [x] Applied to every user-sourced column in the CSV export.
- [x] 12 unit tests in `backend/tests/test_audit_csv.py`.

### 3. Edge nginx hardening ✅
- [x] Listens on `:443` with TLS (certs mounted via `TLS_CERT_DIR`).
- [x] Redirects `:80` → `:443`.
- [x] Ships `Strict-Transport-Security`, `X-Content-Type-Options`,
      `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
      `Permissions-Policy`, strict SPA-compatible CSP.
- [x] `server_tokens off`.
- [x] Provisioning notes in `infra/nginx/README.md`.

### 4. Rate limiting ✅
- [x] App-layer sliding window on `/auth/login`: per-email 10/15min,
      per-IP 30/15min. Redis primary with in-process fallback.
- [x] Nginx `limit_req_zone gs_login` 5r/min per IP, `gs_ingest` 30r/s per
      `X-Gateway-API-Key`, `limit_conn_zone gs_ws` 20/IP.
- [x] Returns `429` with `Retry-After`.

### 5. JSON scalers (drop pickle loading) ✅
- [x] `ai/enviroguard/train.py` + `ai/slopewatch/train.py` emit `scaler.json`.
- [x] `backend/app/services/tflite_runtime.py` loads JSON and refuses
      legacy `scaler.pkl` with a loud error.
- [x] Pickle code path deleted entirely.

### 6. WebSocket JWT auth on `/ws/{site_id}` ✅
- [x] Accepts `?token=<access_jwt>` OR `Sec-WebSocket-Protocol: bearer,<token>`.
- [x] Validates with `decode_token`; `1008` close if invalid.
- [x] Rejects refresh-type JWTs presented as WS credentials.
- [x] Frontend `useWebSocket` appends the token from `authStore`.
- [x] Unit tests in `backend/tests/test_ws_auth.py`.

### 7. Per-gateway credentials ✅
- [x] New `sensor_gateways` table with `key_prefix`, `hashed_key`,
      `allowed_node_ids` JSONB, `active`.
- [x] Alembic migration `0003_sensor_gateways`.
- [x] `/sensors/ingest` looks up gateway by prefix, bcrypt-verifies the
      secret, enforces `allowed_node_ids` per reading.
- [x] Admin endpoints `POST /gateways`, `POST /gateways/{id}/rotate`,
      `POST /gateways/{id}/deactivate`, `GET /gateways`.
- [x] Plaintext returned once at mint time, never again.
- [x] Legacy shared-key path preserved only when `env != production` (the
      config validator blocks the default key in prod).

### 8. Refresh-token revocation + `/auth/logout` ✅
- [x] Both access and refresh JWTs carry a `jti` claim.
- [x] `app/services/token_blocklist.py` — Redis-backed with in-process
      fallback; TTL-scoped blocklist.
- [x] `POST /auth/logout` revokes the caller's refresh token.
- [x] `/auth/refresh` checks the blocklist before issuing new access tokens.
- [x] Frontend `authStore.logout()` POSTs to `/auth/logout`.

### 9. Audit log hash chain ✅
- [x] New columns `audit_log.prev_hash` + `audit_log.row_hash`.
- [x] `audit.record()` computes `row_hash = sha256(prev_hash || canonical_json)`
      on insert.
- [x] Canonical payload excludes hash columns (otherwise self-referential).
- [x] `GET /audit/verify` (esg_admin) walks the chain and reports the first break.
- [x] Alembic migration `0004_audit_hash_chain`.
- [ ] Nightly Celery attestation signing (deferred to Phase 2.2 — needs
      KMS wiring).

### 10. `HttpOnly` refresh cookie + CSRF double-submit ✅
- [x] `/auth/login` sets refresh token as `HttpOnly; Secure; SameSite=Lax`
      cookie scoped to `/api/v1/auth`.
- [x] Companion readable `gs_csrf` cookie + `X-CSRF-Token` header required
      when the refresh cookie is used.
- [x] `/auth/refresh` prefers cookie, falls back to body for transition.
- [x] CSRF token rotated on every refresh.
- [x] `/auth/logout` clears the cookie and revokes the JTI.
- [ ] Frontend SPA migration to `credentials: 'include'` + in-memory access
      token (landed in a follow-up PR; backend supports both paths today).

## Non-goals for Phase 2.1

- Full IdP/SSO — defer to Phase 2.3.
- Per-site RBAC — belongs with notifications in 2.3.
- Field-level encryption at rest — not requested by spec.

## Acceptance

- [x] All backend items above checked.
- [ ] `docs/security-findings.md` — see updated status table.
- [ ] `bandit -r backend/app` clean or reviewed.
- [ ] `npm audit --production` has no Highs.
- [ ] Penetration-test report (internal) filed under `docs/security/`.
