"""notifications + per-site RBAC (Phase 2.3)

Revision ID: 0005_notifications_rbac
Revises: 0004_audit_hash_chain
Create Date: 2026-04-18
"""
from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_notifications_rbac"
down_revision: str | None = "0004_audit_hash_chain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("min_severity", sa.String(16), nullable=False, server_default="CRITICAL"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_notification_subscriptions_user_id", "notification_subscriptions", ["user_id"]
    )
    op.create_index(
        "ix_notification_subscriptions_site_id", "notification_subscriptions", ["site_id"]
    )
    op.create_unique_constraint(
        "uq_notification_sub_user_site_channel",
        "notification_subscriptions",
        ["user_id", "site_id", "channel"],
    )

    op.create_table(
        "user_sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_user_sites_user_id", "user_sites", ["user_id"])
    op.create_index("ix_user_sites_site_id", "user_sites", ["site_id"])
    op.create_unique_constraint("uq_user_site_user_site", "user_sites", ["user_id", "site_id"])

    op.create_table(
        "escalation_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_escalation_steps_site_id", "escalation_steps", ["site_id"])
    op.create_unique_constraint(
        "uq_escalation_site_position", "escalation_steps", ["site_id", "position"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_escalation_site_position", "escalation_steps", type_="unique"
    )
    op.drop_index("ix_escalation_steps_site_id", table_name="escalation_steps")
    op.drop_table("escalation_steps")

    op.drop_constraint("uq_user_site_user_site", "user_sites", type_="unique")
    op.drop_index("ix_user_sites_site_id", table_name="user_sites")
    op.drop_index("ix_user_sites_user_id", table_name="user_sites")
    op.drop_table("user_sites")

    op.drop_constraint(
        "uq_notification_sub_user_site_channel",
        "notification_subscriptions",
        type_="unique",
    )
    op.drop_index(
        "ix_notification_subscriptions_site_id", table_name="notification_subscriptions"
    )
    op.drop_index(
        "ix_notification_subscriptions_user_id", table_name="notification_subscriptions"
    )
    op.drop_table("notification_subscriptions")

    op.drop_column("users", "phone_number")
