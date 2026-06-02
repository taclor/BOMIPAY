"""Add notifications table and extend alert metadata

Revision ID: 0005_notifications_and_alert_extensions
Revises: 0004_alerts
Create Date: 2026-04-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_notifications_and_alert_extensions"
down_revision = "0004_alerts"
branch_labels = None
depend_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("source_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("rule_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unread"),
        sa.Column("delivery_error", sa.String(length=1024), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_merchant_user", "notifications", ["merchant_id", "user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_merchant_user", table_name="notifications")
    op.drop_table("notifications")
    op.drop_column("alerts", "resolved_at")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("alerts", "rule_code")
    op.drop_column("alerts", "source_type")
