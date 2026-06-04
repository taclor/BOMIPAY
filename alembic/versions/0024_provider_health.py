"""Add provider_health_metrics table

Revision ID: 0024_provider_health
Revises: 0023_domain_events
Create Date: 2024-01-16 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "0024_provider_health"
down_revision = "0023_domain_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_health_metrics",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transaction_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transaction_fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transaction_avg_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_avg_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("webhook_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("webhook_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("webhook_fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("webhook_avg_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outage_windows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_outage_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outage_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reliability_score_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_lag_score_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("webhook_failure_score_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.String(length=20), nullable=False, server_default="healthy"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_health_metrics_merchant_id",
        "provider_health_metrics",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_health_metrics_provider_name",
        "provider_health_metrics",
        ["provider_name"],
        unique=False,
    )
    op.create_index(
        "ix_provider_health_metrics_metric_date",
        "provider_health_metrics",
        ["metric_date"],
        unique=False,
    )
    op.create_index(
        "ix_provider_health_metrics_merchant_provider_date",
        "provider_health_metrics",
        ["merchant_id", "provider_name", "metric_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_health_metrics_merchant_provider_date",
        table_name="provider_health_metrics",
    )
    op.drop_index(
        "ix_provider_health_metrics_metric_date",
        table_name="provider_health_metrics",
    )
    op.drop_index(
        "ix_provider_health_metrics_provider_name",
        table_name="provider_health_metrics",
    )
    op.drop_index(
        "ix_provider_health_metrics_merchant_id",
        table_name="provider_health_metrics",
    )
    op.drop_table("provider_health_metrics")
