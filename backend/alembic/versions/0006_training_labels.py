"""training labels (Phase 2.4)

Revision ID: 0006_training_labels
Revises: 0005_notifications_rbac
Create Date: 2026-04-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_training_labels"
down_revision: str | None = "0005_notifications_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("parameter", sa.String(64), nullable=False),
        sa.Column("t_start", sa.DateTime, nullable=False),
        sa.Column("t_end", sa.DateTime, nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_training_labels_site_id", "training_labels", ["site_id"])
    op.create_index("ix_training_labels_node_id", "training_labels", ["node_id"])
    op.create_index(
        "ix_training_labels_site_param", "training_labels", ["site_id", "parameter"]
    )
    op.create_index(
        "ix_training_labels_window", "training_labels", ["t_start", "t_end"]
    )


def downgrade() -> None:
    op.drop_index("ix_training_labels_window", table_name="training_labels")
    op.drop_index("ix_training_labels_site_param", table_name="training_labels")
    op.drop_index("ix_training_labels_node_id", table_name="training_labels")
    op.drop_index("ix_training_labels_site_id", table_name="training_labels")
    op.drop_table("training_labels")
