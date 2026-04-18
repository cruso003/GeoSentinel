"""compliance report Ed25519 signing columns (Phase 3 §IFC PDF)

Revision ID: 0009_report_signing
Revises: 0008_community_opt_in
Create Date: 2026-04-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_report_signing"
down_revision: str | None = "0008_community_opt_in"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "compliance_reports",
        sa.Column("signature_b64", sa.String(128), nullable=True),
    )
    op.add_column(
        "compliance_reports",
        sa.Column("signing_pubkey_hex", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("compliance_reports", "signing_pubkey_hex")
    op.drop_column("compliance_reports", "signature_b64")
