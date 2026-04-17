# Security findings

Catalog from the Phase-2 review (commit `76ff179`). Severity uses CVSS-ish
weighting in the deployed-to-a-customer context. Status is updated as items
land; each closed item should cite a commit.

## Critical — prod blockers

| # | Finding | Fix | Status |
|---|---|---|---|
| S01 | Static `MQTT_GATEWAY_API_KEY` shared across all gateways | Per-gateway DB-stored keys, mTLS, node-scope enforcement | open → Phase 2.1 §7 |
| S02 | `/ws/{site_id}` accepts anonymous connections | Require JWT via `?token=` or `Sec-WebSocket-Protocol` | open → Phase 2.1 §6 |
| S03 | JWTs persisted in `localStorage` (`gs.auth`) | Move access to memory, refresh to `HttpOnly; Secure; SameSite=Lax` cookie; add CSRF token | open → Phase 2.1 §10 |
| S04 | Refresh tokens cannot be revoked; no logout endpoint | `jti` claim + Redis blocklist + `/auth/logout` | open → Phase 2.1 §8 |
| S05 | Audit log rows can be silently modified — no tamper-evidence | Hash-chain each row + nightly signed attestation | open → Phase 2.1 §9 |
| S06 | `/auth/login` has no rate limit or lockout | `slowapi` per-IP + per-email; nginx `limit_req` on ingest | open → Phase 2.1 §4 |

## High

| # | Finding | Fix | Status |
|---|---|---|---|
| S07 | `pickle.load` on `scaler.pkl` from `$GEOSENTINEL_MODEL_DIR` | Ship scalers as signed JSON; drop pickle | open → Phase 2.1 §5 |
| S08 | Edge nginx serves HTTP only; no HSTS/CSP/X-Frame-Options | TLS + security headers | open → Phase 2.1 §3 |
| S09 | CSV formula injection via `audit/export.csv` details/actor | Prefix cells starting with `=+-@\t\r` with `'` | open → Phase 2.1 §2 |
| S10 | `jwt_secret_key` default `"dev-secret-please-replace-please-please"` boots in prod | Pydantic validator rejects defaults when `ENV=production` | open → Phase 2.1 §1 |
| S11 | Passlib bcrypt silently truncates >72-byte passwords | Pre-validate password length | open → Phase 2.1 §1 (small add-on) |

## Medium

| # | Finding | Fix | Status |
|---|---|---|---|
| S12 | CORS `allow_credentials=True` with `allow_methods=["*"]` | Constrain methods/headers explicitly | open → Phase 2.1 §1 add-on |
| S13 | `WSHub.broadcast` serial send — one slow client blocks others | `asyncio.gather(..., return_exceptions=True)` + per-send timeout | open → Phase 2.2 |
| S14 | Celery `--beat` inside worker duplicates schedules at scale | Dedicated `beat` service / redbeat lock | open → Phase 2.2 |
| S15 | Ingest doesn't bind `node_id`/`site_id` to gateway key | Covered by S01 fix | open → Phase 2.1 §7 |
| S16 | Mock `Bearer` tokens persisted and sent to real API | Strip `mock-` tokens from request client | open → functional-gaps |
| S17 | ESA `download_url` pinning | Whitelist the Copernicus host before attaching bearer | open → Phase 3 |

## Low / informational

| # | Finding | Fix | Status |
|---|---|---|---|
| S18 | `datetime.utcnow()` in audit filename | Use timezone-aware UTC | open |
| S19 | `gs_models` volume ownership vs non-root backend user | `chown` at entrypoint | open → Phase 2.2 |
| S20 | Empty `ALLOWED_ORIGINS` → no CORS origins | Validator requires ≥1 entry in prod | open → Phase 2.1 §1 |

## Accepted risk (with justification)

- **Community endpoint unauthenticated.** Intentional per Spec §5.2.7.
  Mitigation: rate-limit at the edge, no sensitive data surfaced, PII
  excluded from response shape.

## Tracking

Every closed row must include the resolving commit SHA and a one-line
verification note. Aim: keep Critical+High at zero before the first
customer pilot go-live.
