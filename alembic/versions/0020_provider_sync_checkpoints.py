"""Add provider_sync_checkpoints table

Revision ID: 0020_provider_sync_checkpoints
Revises: 0019_dashboard_snapshots
Create Date: 2026-06-05 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_provider_sync_checkpoints"
down_revision = "0019_dashboard_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_sync_checkpoints",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("provider_account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("last_synced_timestamp", sa.String(length=255), nullable=True),
        sa.Column("last_page_cursor", sa.String(length=255), nullable=True),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["provider_account_id"], ["provider_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_sync_checkpoints_merchant_id",
        "provider_sync_checkpoints",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_sync_checkpoints_provider_account_id",
        "provider_sync_checkpoints",
        ["provider_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_sync_checkpoints_provider_account_id",
        table_name="provider_sync_checkpoints",
    )
    op.drop_index(
        "ix_provider_sync_checkpoints_merchant_id",
        table_name="provider_sync_checkpoints",
    )
    op.drop_table("provider_sync_checkpoints")
