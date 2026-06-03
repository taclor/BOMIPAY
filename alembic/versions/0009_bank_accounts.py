"""Add bank_accounts table

Revision ID: 0009_bank_accounts
Revises: 0008
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_bank_accounts"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=False),
        sa.Column("bank_code", sa.String(length=64), nullable=True),
        sa.Column("account_number_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="NGN"),
        sa.Column("purpose", sa.String(length=32), nullable=False, server_default="settlement"),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_accounts_merchant_id", "bank_accounts", ["merchant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bank_accounts_merchant_id", table_name="bank_accounts")
    op.drop_table("bank_accounts")
