"""Add provider_sync_jobs table

Revision ID: 0012_provider_sync_jobs
Revises: 0011_bank_statements
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_provider_sync_jobs"
down_revision = "0011_bank_statements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_sync_jobs",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("provider_account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("raw_response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_sync_jobs_merchant", "provider_sync_jobs", ["merchant_id"], unique=False)
    op.create_index("ix_provider_sync_jobs_provider_account", "provider_sync_jobs", ["provider_account_id"], unique=False)
    op.create_index("ix_provider_sync_jobs_correlation", "provider_sync_jobs", ["correlation_id"], unique=False)
    op.create_index("ix_provider_sync_jobs_status", "provider_sync_jobs", ["merchant_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_provider_sync_jobs_status", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_correlation", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_provider_account", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_merchant", table_name="provider_sync_jobs")
    op.drop_table("provider_sync_jobs")
