"""Harden alerts, notifications, and transaction query indexes

Revision ID: 0006_harden_alerts_notifications_transactions
Revises: 0005_notifications_and_alert_extensions
Create Date: 2026-04-11 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_harden_alerts_notifications_transactions"
down_revision = "0005_notifications_and_alert_extensions"
branch_labels = None
depend_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("dedupe_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "alerts",
        sa.Column("first_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_merchant_dedupe", "alerts", ["merchant_id", "dedupe_key"], unique=False)
    op.create_index("ix_alerts_merchant_status", "alerts", ["merchant_id", "status"], unique=False)

    op.add_column(
        "notifications",
        sa.Column("delivery_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("channel_message_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_delivery_key", "notifications", ["delivery_key"], unique=False)
    op.create_index("ix_notifications_user_status", "notifications", ["user_id", "status"], unique=False)
    op.create_index("ix_notifications_merchant_status", "notifications", ["merchant_id", "status"], unique=False)
    op.create_index("ix_notifications_next_retry", "notifications", ["next_retry_at"], unique=False)

    op.create_index("ix_transactions_merchant_status", "transactions", ["merchant_id", "status"], unique=False)
    op.create_index("ix_transactions_merchant_provider", "transactions", ["merchant_id", "provider_name"], unique=False)
    op.create_index("ix_transactions_merchant_created", "transactions", ["merchant_id", "created_at"], unique=False)
    op.create_index("ix_transaction_events_transaction_created", "transaction_events", ["transaction_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transaction_events_transaction_created", table_name="transaction_events")
    op.drop_index("ix_transactions_merchant_created", table_name="transactions")
    op.drop_index("ix_transactions_merchant_provider", table_name="transactions")
    op.drop_index("ix_transactions_merchant_status", table_name="transactions")

    op.drop_index("ix_notifications_next_retry", table_name="notifications")
    op.drop_index("ix_notifications_merchant_status", table_name="notifications")
    op.drop_index("ix_notifications_user_status", table_name="notifications")
    op.drop_index("ix_notifications_delivery_key", table_name="notifications")
    op.drop_column("notifications", "next_retry_at")
    op.drop_column("notifications", "last_attempt_at")
    op.drop_column("notifications", "channel_message_id")
    op.drop_column("notifications", "delivery_key")

    op.drop_index("ix_alerts_merchant_status", table_name="alerts")
    op.drop_index("ix_alerts_merchant_dedupe", table_name="alerts")
    op.drop_column("alerts", "last_triggered_at")
    op.drop_column("alerts", "first_triggered_at")
    op.drop_column("alerts", "occurrence_count")
    op.drop_column("alerts", "dedupe_key")
