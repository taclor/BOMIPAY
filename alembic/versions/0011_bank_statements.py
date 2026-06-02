"""Add bank statement tables

Revision ID: 0011_bank_statements
Revises: 0010_data_sources
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_bank_statements"
down_revision = "0010_data_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("bank_account_id", sa.CHAR(length=36), nullable=True),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_statement_imports_merchant_id", "bank_statement_imports", ["merchant_id"], unique=False)
    op.create_index("ix_bank_statement_imports_bank_account", "bank_statement_imports", ["bank_account_id"], unique=False)

    op.create_table(
        "bank_statement_entries",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("import_id", sa.CHAR(length=36), nullable=False),
        sa.Column("bank_account_id", sa.CHAR(length=36), nullable=True),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("debit_amount_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_amount_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("balance_after_minor", sa.Integer(), nullable=True),
        sa.Column("counterparty_name", sa.String(length=255), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("normalized_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["bank_statement_imports.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_hash", name="uq_bank_statement_entries_hash"),
    )
    op.create_index("ix_bank_statement_entries_merchant_id", "bank_statement_entries", ["merchant_id"], unique=False)
    op.create_index("ix_bank_statement_entries_import_id", "bank_statement_entries", ["import_id"], unique=False)
    op.create_index("ix_bank_statement_entries_entry_date", "bank_statement_entries", ["merchant_id", "entry_date"], unique=False)
    op.create_index("ix_bank_statement_entries_reference", "bank_statement_entries", ["reference"], unique=False)
    op.create_index("ix_bank_statement_entries_hash", "bank_statement_entries", ["normalized_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_bank_statement_entries_hash", table_name="bank_statement_entries")
    op.drop_index("ix_bank_statement_entries_reference", table_name="bank_statement_entries")
    op.drop_index("ix_bank_statement_entries_entry_date", table_name="bank_statement_entries")
    op.drop_index("ix_bank_statement_entries_import_id", table_name="bank_statement_entries")
    op.drop_index("ix_bank_statement_entries_merchant_id", table_name="bank_statement_entries")
    op.drop_table("bank_statement_entries")

    op.drop_index("ix_bank_statement_imports_bank_account", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_merchant_id", table_name="bank_statement_imports")
    op.drop_table("bank_statement_imports")
