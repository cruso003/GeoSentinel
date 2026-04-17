"""sensor gateways — per-gateway credentials

Revision ID: 0003_sensor_gateways
Revises: 0002_audit_log
Create Date: 2026-04-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sensor_gateways"
down_revision: Union[str, None] = "0002_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sensor_gateways",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("hashed_key", sa.String(255), nullable=False),
        sa.Column("allowed_node_ids", sa.JSON, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
    )
    op.create_unique_constraint("uq_sensor_gateways_key_prefix", "sensor_gateways", ["key_prefix"])
    op.create_index("ix_sensor_gateways_site_id", "sensor_gateways", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_sensor_gateways_site_id", table_name="sensor_gateways")
    op.drop_constraint("uq_sensor_gateways_key_prefix", "sensor_gateways", type_="unique")
    op.drop_table("sensor_gateways")
