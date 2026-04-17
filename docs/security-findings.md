# Security findings

Catalog from the Phase-2 review (commit `76ff179`). Severity uses CVSS-ish
weighting in the deployed-to-a-customer context. Status is updated as items
land; each closed item cites a commit.

## Critical — prod blockers

| # | Finding | Fix | Status |
|---|---|---|---|
| S01 | Static `MQTT_GATEWAY_API_KEY` shared across all gateways | Per-gateway DB-stored keys, node-scope enforcement | resolved `816e664` |
| S02 | `/ws/{site_id}` accepts anonymous connections | Require JWT via `?token=` or `Sec-WebSocket-Protocol` | resolved `cc09340` |
| S03 | JWTs persisted in `localStorage` (`gs.auth`) | Refresh in `HttpOnly; Secure; SameSite=Lax` cookie + CSRF double-submit | backend resolved `c8aeeeb`; SPA migration pending |
| S04 | Refresh tokens cannot be revoked; no logout endpoint | `jti` claim + Redis blocklist + `/auth/logout` | resolved `2ab66a1` |
| S05 | Audit log rows can be silently modified — no tamper-evidence | SHA-256 hash chain + `/audit/verify` | resolved `cb1946c` (nightly signed attestation deferred to Phase 2.2) |
| S06 | `/auth/login` has no rate limit or lockout | App-layer sliding window + nginx `limit_req` | resolved `5603e77` |

## High

| # | Finding | Fix | Status |
|---|---|---|---|
| S07 | `pickle.load` on `scaler.pkl` from `$GEOSENTINEL_MODEL_DIR` | Ship scalers as JSON; refuse pickle | resolved `9e35b1f` |
| S08 | Edge nginx serves HTTP only; no HSTS/CSP/X-Frame-Options | TLS + security headers | resolved `5603e77` |
| S09 | CSV formula injection via `audit/export.csv` details/actor | Prefix cells starting with `=+-@\t\r` with `'` | resolved `5603e77` |
| S10 | `jwt_secret_key` default `"dev-secret-please-replace-please-please"` boots in prod | Pydantic validator rejects defaults when `ENV=production` | resolved `5603e77` |
| S11 | Passlib bcrypt silently truncates >72-byte passwords | `_guard_length()` in `hash_password`/`verify_password` | resolved `5603e77` |

## Medium

| # | Finding | Fix | Status |
|---|---|---|---|
| S12 | CORS `allow_credentials=True` with `allow_methods=["*"]` | Constrain methods/headers explicitly | open → Phase 2.2 |
| S13 | `WSHub.broadcast` serial send — one slow client blocks others | `asyncio.gather(..., return_exceptions=True)` + per-send timeout | open → Phase 2.2 |
| S14 | Celery `--beat` inside worker duplicates schedules at scale | Dedicated `beat` service / redbeat lock | open → Phase 2.2 |
| S15 | Ingest doesn't bind `node_id`/`site_id` to gateway key | Covered by S01 fix | resolved `816e664` |
| S16 | Mock `Bearer` tokens persisted and sent to real API | Strip `mock-` tokens from request client | open → functional-gaps |
| S17 | ESA `download_url` pinning | Whitelist the Copernicus host before attaching bearer | open → Phase 3 |

## Low / informational

| # | Finding | Fix | Status |
|---|---|---|---|
| S18 | `datetime.utcnow()` in audit filename | Use timezone-aware UTC | resolved `5603e77` |
| S19 | `gs_models` volume ownership vs non-root backend user | `chown` at entrypoint | open → Phase 2.2 |
| S20 | Empty `ALLOWED_ORIGINS` → no CORS origins | Validator requires ≥1 entry in prod | resolved `5603e77` |

## Accepted risk (with justification)

- **Community endpoint unauthenticated.** Intentional per Spec §5.2.7.
  Mitigation: rate-limit at the edge, no sensitive data surfaced, PII
  excluded from response shape.

## Tracking

Every closed row cites the resolving commit SHA. Critical+High must stay at
zero before the first customer pilot go-live. Current state: Critical S01,
S02, S04, S05, S06 closed; S03 partially closed (backend shipped,
frontend SPA migration tracked as a Phase 2.1 follow-up). All High findings
closed.
