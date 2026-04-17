"""audit log hash chain columns

Revision ID: 0004_audit_hash_chain
Revises: 0003_sensor_gateways
Create Date: 2026-04-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_audit_hash_chain"
down_revision: Union[str, None] = "0003_sensor_gateways"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("row_hash", sa.String(64), nullable=True))
    op.create_index("ix_audit_log_row_hash", "audit_log", ["row_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_row_hash", table_name="audit_log")
    op.drop_column("audit_log", "row_hash")
    op.drop_column("audit_log", "prev_hash")
