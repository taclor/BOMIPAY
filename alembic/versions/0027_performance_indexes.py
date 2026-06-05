"""Add Performance Optimization Indexes

Revision ID: 0027_performance_indexes
Revises: 0026_ai_token_usage
Create Date: 2024-01-18 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0027_performance_indexes"
down_revision = "0026_ai_token_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Transactions table indexes
    # Failed payment list: filter by merchant and status
    op.create_index(
        "ix_transactions_merchant_status_created",
        "transactions",
        ["merchant_id", "status", sa.desc("created_at")],
        unique=False,
    )
    
    # Provider-specific transaction filtering
    op.create_index(
        "ix_transactions_merchant_provider_created",
        "transactions",
        ["merchant_id", "provider_name", sa.desc("created_at")],
        unique=False,
    )

    # Incidents table indexes
    # List active incidents by severity
    op.create_index(
        "ix_incidents_merchant_status_severity_created",
        "incidents",
        ["merchant_id", "status", sa.desc("severity"), sa.desc("created_at")],
        unique=False,
    )
    
    # List incidents for merchant by date
    op.create_index(
        "ix_incidents_merchant_created",
        "incidents",
        ["merchant_id", sa.desc("created_at")],
        unique=False,
    )

    # Provider sync jobs indexes
    # Get sync jobs for a specific provider account
    op.create_index(
        "ix_provider_sync_merchant_provider_created",
        "provider_sync_jobs",
        ["merchant_id", "provider_account_id", sa.desc("created_at")],
        unique=False,
    )
    
    # Filter by sync status
    op.create_index(
        "ix_provider_sync_merchant_status_created",
        "provider_sync_jobs",
        ["merchant_id", "status", sa.desc("created_at")],
        unique=False,
    )

    # Bank statement entries indexes
    # Reconciliation lookups by bank account and date
    op.create_index(
        "ix_bank_statement_entries_merchant_bank_date",
        "bank_statement_entries",
        ["merchant_id", "bank_account_id", sa.desc("entry_date")],
        unique=False,
    )
    
    # Deduplication: find existing entry by hash
    op.create_index(
        "ix_bank_statement_entries_merchant_hash",
        "bank_statement_entries",
        ["merchant_id", "normalized_hash"],
        unique=False,
    )

    # Provider health metrics
    op.create_index(
        "ix_provider_health_metrics_merchant_created",
        "provider_health_metrics",
        ["merchant_id", sa.desc("created_at")],
        unique=False,
    )


def downgrade() -> None:
    # Drop all indexes created by this migration in reverse order
    op.drop_index("ix_provider_health_metrics_merchant_created", table_name="provider_health_metrics")
    
    op.drop_index("ix_bank_statement_entries_merchant_hash", table_name="bank_statement_entries")
    op.drop_index("ix_bank_statement_entries_merchant_bank_date", table_name="bank_statement_entries")
    
    op.drop_index("ix_provider_sync_merchant_status_created", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_merchant_provider_created", table_name="provider_sync_jobs")
    
    op.drop_index("ix_incidents_merchant_created", table_name="incidents")
    op.drop_index("ix_incidents_merchant_status_severity_created", table_name="incidents")
    
    op.drop_index("ix_transactions_merchant_provider_created", table_name="transactions")
    op.drop_index("ix_transactions_merchant_status_created", table_name="transactions")
