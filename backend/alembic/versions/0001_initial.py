"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sites",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("country", sa.String(128), nullable=False),
        sa.Column("centroid_lat", sa.Float, nullable=False),
        sa.Column("centroid_lng", sa.Float, nullable=False),
        sa.Column("boundary_geojson", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "sensor_nodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("node_type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("elevation_m", sa.Float, nullable=False, server_default="0"),
        sa.Column("battery_pct", sa.Integer, nullable=False, server_default="100"),
        sa.Column("signal_rssi", sa.Integer, nullable=False, server_default="-70"),
        sa.Column("last_seen", sa.DateTime, server_default=sa.func.now()),
        sa.Column("status", sa.String(16), nullable=False, server_default="ONLINE"),
        sa.Column("calibration_due", sa.Date, nullable=False),
    )

    op.create_table(
        "mine_slopes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("geometry_geojson", sa.JSON, nullable=False),
        sa.Column("mesh_vertices", sa.JSON, nullable=False),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("parameter", sa.String(32), nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("threshold", sa.Float, nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("acknowledged_by", sa.String(255), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_alerts_site_id", "alerts", ["site_id"])
    op.create_index("ix_alerts_node_id", "alerts", ["node_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("period_start", sa.DateTime, nullable=False),
        sa.Column("period_end", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("download_url", sa.Text, nullable=True),
        sa.Column("data_integrity_hash", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("generated_at", sa.DateTime, nullable=True),
        sa.Column("requested_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "enviroguard_predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("ph_exceedance_24h", sa.Float, nullable=False),
        sa.Column("turbidity_exceedance_24h", sa.Float, nullable=False),
        sa.Column("do_exceedance_24h", sa.Float, nullable=False),
        sa.Column("conductivity_exceedance_24h", sa.Float, nullable=False),
        sa.Column("pm25_exceedance_24h", sa.Float, nullable=False),
        sa.Column("ph_exceedance_72h", sa.Float, nullable=False),
        sa.Column("turbidity_exceedance_72h", sa.Float, nullable=False),
        sa.Column("overall_risk_24h", sa.String(16), nullable=False),
        sa.Column("overall_risk_72h", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
    )

    op.create_table(
        "slopewatch_predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(64), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("slope_id", sa.String(64), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("alert_tier", sa.String(16), nullable=False),
        sa.Column("pore_pressure_factor", sa.Float, nullable=False),
        sa.Column("tilt_factor", sa.Float, nullable=False),
        sa.Column("insar_factor", sa.Float, nullable=False),
        sa.Column("rainfall_factor", sa.Float, nullable=False),
        sa.Column("trend", sa.String(16), nullable=False),
        sa.Column("trend_rate", sa.Float, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("slopewatch_predictions")
    op.drop_table("enviroguard_predictions")
    op.drop_table("compliance_reports")
    op.drop_index("ix_alerts_created_at", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_node_id", table_name="alerts")
    op.drop_index("ix_alerts_site_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("mine_slopes")
    op.drop_table("sensor_nodes")
    op.drop_table("sites")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
