"""Provider sync job enhancements with retry and backoff support."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_provider_sync_enhancements"
down_revision = "0016_bank_statement_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to provider_sync_jobs table for retry and backoff support
    op.add_column(
        "provider_sync_jobs",
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("error_severity", sa.String(32), nullable=True),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("backoff_multiplier", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "provider_sync_jobs",
        sa.Column("failure_details", sa.JSON(), nullable=True),
    )
    
    # Add index on next_retry_at for efficient scheduling
    op.create_index(
        "ix_provider_sync_jobs_next_retry_at",
        "provider_sync_jobs",
        ["next_retry_at"],
    )
    
    # Replace the old composite index (merchant_id, status) with a simpler status-only index
    op.drop_index("ix_provider_sync_jobs_status", table_name="provider_sync_jobs")
    op.create_index(
        "ix_provider_sync_jobs_status",
        "provider_sync_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_sync_jobs_status", table_name="provider_sync_jobs")
    # Restore original composite index from migration 0012
    op.create_index("ix_provider_sync_jobs_status", "provider_sync_jobs", ["merchant_id", "status"], unique=False)
    op.drop_index("ix_provider_sync_jobs_next_retry_at", table_name="provider_sync_jobs")
    op.drop_column("provider_sync_jobs", "failure_details")
    op.drop_column("provider_sync_jobs", "backoff_multiplier")
    op.drop_column("provider_sync_jobs", "next_retry_at")
    op.drop_column("provider_sync_jobs", "max_retries")
    op.drop_column("provider_sync_jobs", "retry_count")
    op.drop_column("provider_sync_jobs", "error_severity")
    op.drop_column("provider_sync_jobs", "records_failed")
