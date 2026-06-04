"""Add ledger foundation tables

Revision ID: 0021_ledger_foundation
Revises: 0020_provider_sync_checkpoints
Create Date: 2026-06-10 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_ledger_foundation"
down_revision = "0020_provider_sync_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ledger_accounts table
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ledger_accounts_merchant_id",
        "ledger_accounts",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_ledger_accounts_merchant_account_code",
        "ledger_accounts",
        ["merchant_id", "account_code"],
        unique=True,
    )

    # Create journal_entries table
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("transaction_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["ledger_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_journal_entries_merchant_id",
        "journal_entries",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_journal_entries_account_id",
        "journal_entries",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_journal_entries_transaction_id",
        "journal_entries",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        "ix_journal_entries_idempotency_key",
        "journal_entries",
        ["idempotency_key"],
        unique=True,
    )

    # Create ledger_lines table
    op.create_table(
        "ledger_lines",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("journal_entry_id", sa.CHAR(length=36), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_type", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_minor > 0", name="check_ledger_lines_amount_positive"),
        sa.CheckConstraint("line_type IN ('DEBIT', 'CREDIT')", name="check_ledger_lines_type"),
    )
    op.create_index(
        "ix_ledger_lines_journal_entry_id",
        "ledger_lines",
        ["journal_entry_id"],
        unique=False,
    )

    # Create fee_records table
    op.create_table(
        "fee_records",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("journal_entry_id", sa.CHAR(length=36), nullable=False),
        sa.Column("fee_type", sa.String(length=64), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount_minor > 0", name="check_fee_records_amount_positive"),
    )
    op.create_index(
        "ix_fee_records_merchant_id",
        "fee_records",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_fee_records_journal_entry_id",
        "fee_records",
        ["journal_entry_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fee_records_journal_entry_id", table_name="fee_records")
    op.drop_index("ix_fee_records_merchant_id", table_name="fee_records")
    op.drop_table("fee_records")
    
    op.drop_index("ix_ledger_lines_journal_entry_id", table_name="ledger_lines")
    op.drop_table("ledger_lines")
    
    op.drop_index("ix_journal_entries_idempotency_key", table_name="journal_entries")
    op.drop_index("ix_journal_entries_transaction_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_account_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_merchant_id", table_name="journal_entries")
    op.drop_table("journal_entries")
    
    op.drop_index("ix_ledger_accounts_merchant_account_code", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_merchant_id", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
