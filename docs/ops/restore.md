# Restore runbook

Recovery procedures for the GeoSentinel production deployment. This is a
living document — walk it end-to-end during each quarterly DR drill and
update any steps that drift.

## Inventory of state

| System | Where | Backup cadence | RPO | RTO |
|---|---|---|---|---|
| Postgres | `postgres` compose service, `gs_pg` volume | nightly `pg_dump` → S3 Object-Lock bucket | 24 h | 1 h |
| InfluxDB | `influxdb` service, `gs_influx` volume | nightly `influx backup` → S3 | 24 h | 2 h |
| Redis | `redis` service, `gs_redis` volume | AOF + RDB on-disk; not backed up off-site (ephemeral rate-limit + blocklist state) | — | — |
| Model artifacts | `gs_models` volume | versioned `rsync` to S3 on every retrain | per retrain | 15 min |
| Audit chain | lives in Postgres `audit_log`; hash chain self-verifies | covered by Postgres backup | 24 h | see DB row |

## Prerequisites

- Target host has access to the backup bucket (IAM role / static creds in
  `/etc/geosentinel/aws.env`).
- Operator has `root`-level compose access and a recent `.env` file with
  production secrets.
- `docker compose -f docker-compose.prod.yml` resolves cleanly.

## Postgres restore

```
aws s3 cp s3://gs-backups/postgres/<date>/geosentinel.sql.gz - \
  | gunzip \
  | docker compose -f docker-compose.prod.yml exec -T postgres \
      psql -U geosentinel geosentinel
```

Then verify:

```
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.services import audit; import asyncio; \
             from app.core.db import SessionLocal; \
             asyncio.run((lambda: (_ := SessionLocal()))())"
curl -s http://localhost:8000/api/v1/audit/verify -H "Authorization: Bearer $TOKEN" | jq
```

`audit/verify` must return `{ok: true}` before traffic is re-enabled. A
break means the restore captured a partial write — pull the previous
night's backup and retry.

## Influx restore

```
aws s3 sync s3://gs-backups/influx/<date>/ /tmp/influx-restore/
docker compose -f docker-compose.prod.yml exec -T influxdb \
  influx restore /tmp/influx-restore
```

Verify: `curl -H "Authorization: Token ${INFLUXDB_TOKEN}" http://localhost:8086/ready`.

## Model artifacts

Models are immutable once written. If the volume is lost, pull the last
versioned bundle:

```
aws s3 sync s3://gs-models/$(cat /etc/geosentinel/model-version)/ \
  /var/lib/docker/volumes/gs_models/_data/
```

Backend `/api/v1/ai/*/status` will report `synthetic` until a real bundle
is present.

## Partial failure: audit chain break

If `/api/v1/audit/verify` reports `{ok: false, broken_at: <id>}`:

1. Freeze writes — scale `backend` to 0.
2. Pull the previous night's `pg_dump` into a scratch DB.
3. `audit_log` diff between the two identifies the tampered row.
4. File an incident, preserve both DBs for forensics, then restore from
   the good backup.

## DR drill checklist

- [ ] Restore Postgres from the latest nightly into a throwaway compose env.
- [ ] Restore Influx from the latest nightly.
- [ ] Pull the current model bundle.
- [ ] Boot backend, confirm `/health/ready` returns 200.
- [ ] Confirm `/api/v1/audit/verify` returns `{ok: true}`.
- [ ] Replay a synthetic ingest payload; confirm the alert engine fires.
- [ ] Record elapsed time; compare against the RTO table above.
