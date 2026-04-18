# Phase 2.3 — Notifications + RBAC

Goal: actually deliver CRITICAL alerts to the right humans, and scope each
user to the sites they are allowed to see.

Status: **landed.** Frontend Profile + ESG Subscribers pages now render the
existing API surface. Commits: `e1e6dee` (subscriptions schema,
`require_site_role`, escalation sweep, local-language templates,
profile/subscription/test-alert/admin endpoints), + the Phase 2.3 UI slice.

## Checklist

### Subscription schema
- [x] `notification_subscription(id, user_id, site_id, channel, min_severity,
      active, created_at)` — channel ∈ `{email, sms, push}`; `push` is
      reserved for a later PWA push-notification follow-up and is currently
      a no-op at dispatch.
- [x] `user.phone_number` E.164 column; `validate_e164()` helper in
      `app/services/notifications.py`, plus Pydantic validator on the
      profile PATCH body.
- [x] Alembic migration `0005_notifications_rbac.py` + seed rows for the
      Tokadeh demo users (admin + operator, 2 channels each, min=CRITICAL).

### Wire `_recipients_for_site`
- [x] `NotificationService._recipients_for_site()` joins
      `notification_subscriptions` × `users`, filters by site + severity
      rank (`min_severity ≤ incoming`), and returns `(email, phone)` rows
      the dispatcher dedupes across channels.
- [x] Unit coverage: severity ranking, E.164 validator, template fallback
      tests in `backend/tests/test_notifications.py`.

### UI
- [x] Profile page at `/operations/profile`
      (`frontend/src/views/OperationsView/ProfileTab.tsx`): edits name +
      E.164 phone (`PATCH /profile`), and toggles a per-site × channel
      matrix with a minimum-severity select. Mock mode is local-only
      (nothing persists) so scenario walkthroughs stay side-effect free.
- [x] ESG admin Subscribers tab at `/esg/subscribers` (`SubscribersTab.tsx`):
      searchable + filterable table backed by `GET /admin/subscribers`,
      with CSV export generated client-side.
- [x] Test-alert button per channel row. Hits `POST /subscriptions/test`
      with the current site + channel; surfaces a status banner with the
      provider-noop case called out explicitly.

### Per-site RBAC
- [x] `user_sites(user_id, site_id, role)` join table, migrated + seeded.
- [x] `require_site_role(...)` FastAPI dep in `app/core/deps.py`;
      `allowed_site_ids()` + `user_can_access_site()` in
      `app/services/rbac.py` for manual checks on body-scoped routes.
- [x] Updated `/sites`, `/sites/{site_id}*`, `/alerts`, `/alerts/*`,
      `/ai/*/predictions/{site_id}`, `/ai/*/run` to scope by membership.
- [x] Frontend scope endpoint `GET /me/sites` returns only sites the user
      can access.
- [x] Ingest gateway scope (Phase 2.1 §7) already covers the device side.

### Escalation
- [x] Unacknowledged CRITICAL / EVACUATION alerts escalate to the next
      responder after `ESCALATION_DWELL = 5 min`.
- [x] Chain stored per site in `escalation_steps(site_id, position, user_id)`;
      the seeder installs a two-hop ladder for Tokadeh.
- [x] Each hop writes an `escalation_hop` audit row with `hop=N` details,
      and stamps `[esc:N]` in the alert's `notes` so the sweep is
      idempotent. Celery beat runs the sweep once per minute.

### Community channel
- [x] Local-language SMS templates live under
      `backend/app/services/notifications_templates/` — English, Mano, Gio.
      `render(language, key, **fields)` falls back to English, then to a
      generic one-liner, so new alert types never silence the channel.
- [ ] Community opt-in via a public signup form with SMS confirmation.
      *(Follow-up — ties into the Phase 3 community PWA.)*
- [ ] GDPR/personal-data retention policy documented. *(Follow-up.)*

### Digests
- [x] Daily email digest (`app.services.digest.build_digests` +
      `app.tasks.digest.send_daily_digest`, beat 07:00 UTC, `default`
      queue). Rolls up the last 24 h of WARNING+ alerts per subscribed
      site for every user with an active email subscription, skips users
      subscribed only at CRITICAL (they already got real-time pages),
      and dedupes per (user, UTC date) via an audit-log
      `digest_sent` row so re-running the task inside the same day is a
      no-op. Unit coverage: `backend/tests/test_digest.py`.
- [ ] Weekly IFC summary PDF for ESG admins (see Phase 3 for the full
      report pipeline).

### Acceptance

- [ ] End-to-end test: CRITICAL alert arrives via WS and via email/SMS
      within 30 s to a real subscriber. *(Blocked on a real SMTP + Twilio
      staging account — the dispatcher logs the noop until then.)*
- [x] A user with no `user_site` rows gets an empty dashboard and zero
      alerts. *(Covered by the RBAC scope helpers + integration test of
      `allowed_site_ids` returning `[]`.)*
- [ ] Subscription preferences page verified against a11y (axe) ≥ 95.
      *(Follow-up with the UI slice.)*
