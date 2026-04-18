"""convert DateTime columns to TIMESTAMPTZ

Every datetime the service layer produces is tz-aware
(``datetime.now(UTC)``), but the original models declared
``DateTime`` without ``timezone=True``. Postgres created the columns as
``TIMESTAMP WITHOUT TIME ZONE`` and asyncpg then refused tz-aware
datetime values at insert/compare time — the seed script and the
escalation sweep both crashed on first run against a real Postgres.

This migration aligns the schema with the Python types by altering every
affected column to ``TIMESTAMPTZ``. Existing values are assumed to have
been written as UTC (they were, by the seed + services), so
``USING col AT TIME ZONE 'UTC'`` reinterprets them without shifting the
instant.

Revision ID: 0010_tz_aware_datetimes
Revises: 0009_report_signing
Create Date: 2026-04-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_tz_aware_datetimes"
down_revision: str | None = "0009_report_signing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, column, nullable) triples for every DateTime column in the
# schema. Kept explicit so the downgrade path is symmetric and a reviewer
# can eyeball the full set.
_COLUMNS: list[tuple[str, str, bool]] = [
    ("sites", "created_at", False),
    ("sensor_nodes", "last_seen", False),
    ("alerts", "created_at", False),
    ("alerts", "acknowledged_at", True),
    ("users", "created_at", False),
    ("users", "last_login_at", True),
    ("audit_log", "created_at", False),
    ("enviroguard_predictions", "timestamp", False),
    ("slopewatch_predictions", "timestamp", False),
    ("notification_subscriptions", "created_at", False),
    ("user_sites", "created_at", False),
    ("escalation_steps", "created_at", False),
    ("community_opt_ins", "expires_at", False),
    ("community_opt_ins", "confirmed_at", True),
    ("community_opt_ins", "created_at", False),
    ("sensor_gateways", "created_at", False),
    ("sensor_gateways", "last_used_at", True),
    ("model_versions", "created_at", False),
    ("model_versions", "promoted_at", True),
    ("training_labels", "t_start", False),
    ("training_labels", "t_end", False),
    ("training_labels", "created_at", False),
    ("compliance_reports", "period_start", False),
    ("compliance_reports", "period_end", False),
    ("compliance_reports", "created_at", False),
    ("compliance_reports", "generated_at", True),
]


def _alter(table: str, column: str, *, nullable: bool, to_tz: bool) -> None:
    # SQLite can't ALTER COLUMN TYPE the way Postgres can; this migration
    # is Postgres-only (the dev compose stack uses postgres:16). If we
    # ever run it elsewhere, emit a no-op — the column affinity is
    # already compatible in SQLite.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(timezone=to_tz),
        existing_type=sa.DateTime(timezone=not to_tz),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    for table, column, nullable in _COLUMNS:
        _alter(table, column, nullable=nullable, to_tz=True)


def downgrade() -> None:
    for table, column, nullable in _COLUMNS:
        _alter(table, column, nullable=nullable, to_tz=False)
