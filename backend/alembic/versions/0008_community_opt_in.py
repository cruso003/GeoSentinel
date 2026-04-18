"""community opt-in pending table (Phase 2.3 §Community)

Revision ID: 0008_community_opt_in
Revises: 0007_model_registry
Create Date: 2026-04-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_community_opt_in"
down_revision: str | None = "0007_model_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "community_opt_ins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "phone_number", "site_id", name="uq_community_opt_in_phone_site"
        ),
    )
    op.create_index(
        "ix_community_opt_in_phone_site_expires",
        "community_opt_ins",
        ["phone_number", "site_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_community_opt_in_phone_site_expires", table_name="community_opt_ins"
    )
    op.drop_table("community_opt_ins")
