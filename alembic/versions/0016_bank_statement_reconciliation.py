"""Add bank statement reconciliation support and XLSX import

Revision ID: 0016_bank_statement_reconciliation
Revises: 0015_bank_account_last4_and_data_source_link
Create Date: 2026-06-03 11:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_bank_statement_reconciliation"
down_revision = "0015_bank_account_last4_and_data_source_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add data_source_id to bank_statement_imports
    with op.batch_alter_table("bank_statement_imports") as batch_op:
        batch_op.add_column(sa.Column("data_source_id", sa.CHAR(length=36), nullable=True))
        batch_op.create_index("ix_bank_statement_imports_data_source_id", ["data_source_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_bank_statement_imports_data_source_id",
            "data_sources",
            ["data_source_id"],
            ["id"],
        )

    # Create bank_statement_reconciliations table
    op.create_table(
        "bank_statement_reconciliations",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("import_id", sa.CHAR(length=36), nullable=False),
        sa.Column("entry_id", sa.CHAR(length=36), nullable=False),
        sa.Column("transaction_id", sa.CHAR(length=36), nullable=True),
        sa.Column("match_status", sa.String(length=32), nullable=False, server_default="unmatched"),
        sa.Column("confidence_score_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_bank_statement_reconciliations_merchant_id"),
        sa.ForeignKeyConstraint(["import_id"], ["bank_statement_imports.id"], name="fk_bank_statement_reconciliations_import_id"),
        sa.ForeignKeyConstraint(["entry_id"], ["bank_statement_entries.id"], name="fk_bank_statement_reconciliations_entry_id"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], name="fk_bank_statement_reconciliations_transaction_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_statement_reconciliations_merchant_id", "bank_statement_reconciliations", ["merchant_id"], unique=False)
    op.create_index("ix_bank_statement_reconciliations_import_id", "bank_statement_reconciliations", ["import_id"], unique=False)
    op.create_index("ix_bank_statement_reconciliations_entry_id", "bank_statement_reconciliations", ["entry_id"], unique=False)
    op.create_index("ix_bank_statement_reconciliations_transaction_id", "bank_statement_reconciliations", ["transaction_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bank_statement_reconciliations_transaction_id", table_name="bank_statement_reconciliations")
    op.drop_index("ix_bank_statement_reconciliations_entry_id", table_name="bank_statement_reconciliations")
    op.drop_index("ix_bank_statement_reconciliations_import_id", table_name="bank_statement_reconciliations")
    op.drop_index("ix_bank_statement_reconciliations_merchant_id", table_name="bank_statement_reconciliations")
    op.drop_table("bank_statement_reconciliations")

    with op.batch_alter_table("bank_statement_imports") as batch_op:
        batch_op.drop_constraint("fk_bank_statement_imports_data_source_id", type_="foreignkey")
        batch_op.drop_index("ix_bank_statement_imports_data_source_id")
        batch_op.drop_column("data_source_id")
