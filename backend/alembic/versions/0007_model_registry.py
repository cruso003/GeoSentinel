"""model registry (Phase 2.4 §5)

Revision ID: 0007_model_registry
Revises: 0006_training_labels
Create Date: 2026-04-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_model_registry"
down_revision: str | None = "0006_training_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("version", sa.String(128), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False, server_default="candidate"),
        sa.Column("data_sha256", sa.String(64), nullable=True),
        sa.Column("metrics_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("artifact_uri", sa.String(500), nullable=True),
        sa.Column("mlflow_run_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("promoted_at", sa.DateTime, nullable=True),
        sa.Column("promoted_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
    )
    op.create_index(
        "ix_model_versions_name_stage", "model_versions", ["name", "stage"]
    )


def downgrade() -> None:
    op.drop_index("ix_model_versions_name_stage", table_name="model_versions")
    op.drop_table("model_versions")
