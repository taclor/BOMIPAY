"""Add dashboard_snapshots table

Revision ID: 0019_dashboard_snapshots
Revises: 0018_money_at_risk
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_dashboard_snapshots"
down_revision = "0018_money_at_risk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_snapshots",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_transactions_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount_processed", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
        sa.Column("avg_settlement_time_hours", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"),
        sa.Column("provider_statuses", sa.JSON(), nullable=True),
        sa.Column("incident_count_open", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("money_at_risk_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("alerts", sa.JSON(), nullable=True),
        sa.Column("failed_transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_settlements_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reconciliation_mismatches_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anomaly_indicators", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_snapshots_merchant_id",
        "dashboard_snapshots",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_snapshots_snapshot_time",
        "dashboard_snapshots",
        ["snapshot_time"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_snapshots_merchant_time",
        "dashboard_snapshots",
        ["merchant_id", "snapshot_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_snapshots_merchant_time", table_name="dashboard_snapshots")
    op.drop_index("ix_dashboard_snapshots_snapshot_time", table_name="dashboard_snapshots")
    op.drop_index("ix_dashboard_snapshots_merchant_id", table_name="dashboard_snapshots")
    op.drop_table("dashboard_snapshots")
