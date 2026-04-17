# Phase 2.1 — Security hardening

**Deploy gate.** Do not expose GeoSentinel to customer or gateway traffic until
items 1–5 below land.

## Checklist

### 1. Strict production config validator
- [ ] Add a Pydantic `@field_validator` that rejects default/empty values for
      `jwt_secret_key`, `influxdb_token`, `mqtt_gateway_api_key`, and
      `allowed_origins` when `env == "production"`.
- [ ] Reject `jwt_secret_key` shorter than 32 chars.
- [ ] Fail fast on boot with a clear error.
- [ ] Unit-test: construct `Settings(env="production", jwt_secret_key="dev-...")` → raises.

### 2. CSV formula-injection escape in `/audit/export.csv`
- [ ] Escape cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` by prefixing `'`.
- [ ] Apply to every user-sourced column (`actor_email`, `details`,
      `target_id`, `site_id`).
- [ ] Unit-test: row with `details='=1+1'` exports as `'=1+1`.

### 3. Edge nginx hardening
- [ ] Listen on `:443` with TLS (ACME via Certbot sidecar or external LB).
- [ ] Redirect `:80` → `:443`.
- [ ] Add `Strict-Transport-Security`, `X-Content-Type-Options`,
      `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
      `Content-Security-Policy` (strict, SPA-compatible).
- [ ] Disable `server_tokens`.
- [ ] Test with `curl -I` and Mozilla Observatory score ≥ A.

### 4. Rate limiting
- [ ] `slowapi` on `/auth/login` (5/min per IP + per email).
- [ ] Nginx `limit_req_zone` on `/api/v1/sensors/ingest` (per gateway key).
- [ ] Nginx `limit_conn_zone` on `/ws/` (per IP, ≤ 20 concurrent).
- [ ] Return `429` with retry-after header.

### 5. JSON scalers (drop pickle loading)
- [ ] `ai/enviroguard/train.py` + `ai/slopewatch/train.py` write
      `scaler.json` with `{mean, scale}` instead of `scaler.pkl`.
- [ ] `backend/app/services/tflite_runtime.py` loads JSON not pickle.
- [ ] Delete the pickle code path entirely.
- [ ] Regenerate any committed scalers.

### 6. WebSocket JWT auth on `/ws/{site_id}`
- [ ] Accept `?token=<access_jwt>` OR `Sec-WebSocket-Protocol: bearer,<token>`.
- [ ] Validate with `decode_token`; `4401` close if invalid.
- [ ] Enforce `payload['role']` against the site: community is unauth (on a
      separate path), operator/esg_admin must resolve to the site's org.
- [ ] Frontend `useWebSocket` appends the token from `authStore`.
- [ ] Integration test: connect without token → 4401; with expired token → 4401.

### 7. Per-gateway credentials
- [ ] New table `sensor_gateway(id, site_id, name, key_hash, allowed_node_ids JSONB, created_at, revoked_at)`.
- [ ] Alembic migration.
- [ ] `/sensors/ingest` looks up gateway by header → verifies `allowed_node_ids`
      for every reading; reject mismatched rows.
- [ ] Admin endpoint to rotate keys (returns plaintext once, stores hash).
- [ ] Migration path: provisional gateway seeded at install.
- [ ] Drop the single `MQTT_GATEWAY_API_KEY` env var.

### 8. Refresh-token revocation + `/auth/logout`
- [ ] Issue refresh tokens with a `jti` claim.
- [ ] On `/auth/login`, register `jti` in Redis with TTL = refresh lifetime.
- [ ] On `/auth/logout`, delete the `jti` (blocklist = absence).
- [ ] Alternative: blocklist table keyed by `jti` until `exp`.
- [ ] `decode_token` rejects tokens whose `jti` is not registered.
- [ ] Frontend `logout()` hits the endpoint.

### 9. Audit log hash chain
- [ ] Add columns `audit_log.prev_hash` and `audit_log.row_hash`.
- [ ] On insert: `row_hash = sha256(prev_hash || canonical_json(row_minus_hashes))`.
- [ ] A row's `prev_hash` references the latest committed row's `row_hash`.
- [ ] Nightly Celery task signs the latest `row_hash` with a long-lived key and
      writes the signature to `audit_attestation`.
- [ ] Admin endpoint `/audit/verify` walks the chain, reports first break.

### 10. `HttpOnly` refresh cookie + in-memory access token + CSRF
- [ ] Backend: `/auth/login` sets refresh in `HttpOnly; Secure; SameSite=Lax`
      cookie scoped to `/auth`.
- [ ] Backend: `/auth/refresh` reads cookie (no body).
- [ ] Frontend: `authStore` no longer persists access/refresh; access lives in
      memory; refresh happens automatically via fetch interceptor on 401.
- [ ] Issue a CSRF token cookie (`readable by JS`) + `X-CSRF-Token` header
      requirement on mutating routes.
- [ ] Remove `refresh_token` from `AuthSession` response.
- [ ] Integration test: stale tab survives refresh via cookie; logout clears.

## Non-goals for Phase 2.1

- Full IdP/SSO — defer to Phase 2.3.
- Per-site RBAC — belongs with notifications in 2.3.
- Field-level encryption at rest — not requested by spec.

## Acceptance

- [ ] All items above checked.
- [ ] `docs/security-findings.md` Critical/High items marked resolved.
- [ ] `bandit -r backend/app` clean or reviewed.
- [ ] `npm audit --production` has no Highs.
- [ ] Penetration-test report (internal) filed under `docs/security/`.
