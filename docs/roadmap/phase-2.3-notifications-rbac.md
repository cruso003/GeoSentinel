# Phase 2.3 — Notifications + RBAC

Goal: actually deliver CRITICAL alerts to the right humans, and scope each
user to the sites they are allowed to see.

## Checklist

### Subscription schema
- [ ] `notification_subscription(id, user_id, site_id, channel, min_severity,
      active, created_at)` where `channel ∈ {email, sms, push}`.
- [ ] `user.phone_number E164` column + validator.
- [ ] Alembic migration + seed for demo users.

### Wire `_recipients_for_site`
- [ ] Query subscriptions filtered by `site_id` + `min_severity ≤ incoming`.
- [ ] Return `(email, phone)` tuples de-duped.
- [ ] Include unit test that asserts Critical → real addresses returned.

### UI
- [ ] Profile page: notification preferences toggle per site + channel.
- [ ] ESG admin page: impersonate-free view of who is subscribed to what.
- [ ] Test-alert button (dispatches a dummy WARNING to the current user).

### Per-site RBAC
- [ ] `user_site(user_id, site_id, role)` join table.
- [ ] `require_roles` becomes `require_site_role(site_id, roles)`.
- [ ] Update every route that takes `site_id` to scope queries.
- [ ] Frontend: sites endpoint returns only sites the user can access.
- [ ] Ingest gateway scope (Phase 2.1 §7) already covers device side.

### Escalation
- [ ] Unacknowledged CRITICAL escalates to the next responder after 5 min.
- [ ] Escalation chain stored per site.
- [ ] Records an audit entry at each hop.

### Community channel
- [ ] Local-language SMS templates (English, Mano, Gio) under
      `backend/app/services/notifications_templates/`.
- [ ] Community opt-in via a public signup form with SMS confirmation.
- [ ] GDPR/personal-data retention policy documented.

### Digests
- [ ] Daily email digest of WATCH/WARNING events for subscribed operators.
- [ ] Weekly IFC summary PDF for ESG admins (see Phase 3 for full report).

### Acceptance

- [ ] End-to-end test: CRITICAL alert arrives via WS and via email/SMS within
      30 s to a real subscriber.
- [ ] A user with no `user_site` rows gets an empty dashboard and zero alerts.
- [ ] Subscription preferences page verified against a11y (axe) ≥ 95.
