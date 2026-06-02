"""Add reconciliation engine tables and indexes

Revision ID: 0007_reconciliation_engine
Revises: 0006_harden_alerts_notifications_transactions
Create Date: 2026-04-11 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_reconciliation_engine"
down_revision = "0006_harden_alerts_notifications_transactions"
branch_labels = None
depend_on = None


def upgrade() -> None:
    expected_payment_status = sa.Enum(
        "pending",
        "matched",
        "reconciled",
        "canceled",
        name="expectedpaymentstatus",
        native_enum=False,
        create_constraint=False,
    )
    reconciliation_run_status = sa.Enum(
        "pending",
        "running",
        "completed",
        "failed",
        name="reconciliationrunstatus",
        native_enum=False,
        create_constraint=False,
    )
    reconciliation_match_status = sa.Enum(
        "matched",
        "partial",
        "unmatched",
        "duplicate",
        name="reconciliationmatchstatus",
        native_enum=False,
        create_constraint=False,
    )

    op.create_table(
        "expected_payment_import_batches",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expected_payment_import_batches_merchant", "expected_payment_import_batches", ["merchant_id"], unique=False)

    op.create_table(
        "expected_payments",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("import_batch_id", sa.CHAR(length=36), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("customer_phone", sa.String(length=24), nullable=True),
        sa.Column("status", expected_payment_status, nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["expected_payment_import_batches.id"], ),
    )
    op.create_index("ix_expected_payments_merchant_reference", "expected_payments", ["merchant_id", "reference"], unique=False)
    op.create_index("ix_expected_payments_due_date", "expected_payments", ["merchant_id", "due_date"], unique=False)
    op.create_index(
        "ix_expected_payments_unique_key",
        "expected_payments",
        ["merchant_id", "reference", "amount", "currency", "due_date"],
        unique=True,
    )

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_name", sa.String(length=255), nullable=True),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matching_policy_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("source_expected_payment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", reconciliation_run_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_runs_merchant", "reconciliation_runs", ["merchant_id"], unique=False)
    op.create_index("ix_reconciliation_runs_merchant_created", "reconciliation_runs", ["merchant_id", "created_at"], unique=False)

    op.create_table(
        "reconciliation_results",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_id", sa.CHAR(length=36), nullable=False),
        sa.Column("expected_payment_id", sa.CHAR(length=36), nullable=False),
        sa.Column("transaction_id", sa.CHAR(length=36), nullable=True),
        sa.Column("match_status", reconciliation_match_status, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "expected_payment_id", name="uq_reconciliation_results_run_expected"),
    )
    op.create_index("ix_reconciliation_results_run", "reconciliation_results", ["run_id"], unique=False)
    op.create_index("ix_reconciliation_results_expected", "reconciliation_results", ["expected_payment_id"], unique=False)
    op.create_index("ix_reconciliation_results_transaction", "reconciliation_results", ["transaction_id"], unique=False)
    op.create_index("ix_reconciliation_results_run_status", "reconciliation_results", ["run_id", "match_status"], unique=False)

    op.create_table(
        "settlements",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("settlement_reference", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_settlements_merchant", "settlements", ["merchant_id"], unique=False)
    op.create_index("ix_settlements_provider_settled", "settlements", ["merchant_id", "provider_name", "settled_at"], unique=False)
    op.create_index("ix_settlements_reference", "settlements", ["settlement_reference"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_settlements_reference", table_name="settlements")
    op.drop_index("ix_settlements_provider_settled", table_name="settlements")
    op.drop_index("ix_settlements_merchant", table_name="settlements")
    op.drop_table("settlements")

    op.drop_index("ix_reconciliation_results_run_status", table_name="reconciliation_results")
    op.drop_index("ix_reconciliation_results_transaction", table_name="reconciliation_results")
    op.drop_index("ix_reconciliation_results_expected", table_name="reconciliation_results")
    op.drop_index("ix_reconciliation_results_run", table_name="reconciliation_results")
    op.drop_table("reconciliation_results")

    op.drop_index("ix_reconciliation_runs_merchant_created", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_merchant", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")

    op.drop_index("ix_expected_payments_unique_key", table_name="expected_payments")
    op.drop_index("ix_expected_payments_due_date", table_name="expected_payments")
    op.drop_index("ix_expected_payments_merchant_reference", table_name="expected_payments")
    op.drop_table("expected_payments")

    op.drop_index("ix_expected_payment_import_batches_merchant", table_name="expected_payment_import_batches")
    op.drop_table("expected_payment_import_batches")
