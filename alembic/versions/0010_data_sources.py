"""Add data_sources table

Revision ID: 0010_data_sources
Revises: 0009_bank_accounts
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_data_sources"
down_revision = "0009_bank_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_setup"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.String(length=1024), nullable=True),
        sa.Column("configuration_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_sources_merchant_id", "data_sources", ["merchant_id"], unique=False)
    op.create_index("ix_data_sources_merchant_type", "data_sources", ["merchant_id", "source_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_sources_merchant_type", table_name="data_sources")
    op.drop_index("ix_data_sources_merchant_id", table_name="data_sources")
    op.drop_table("data_sources")
