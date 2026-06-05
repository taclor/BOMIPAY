"""Enhance settlements table: add provider_account_id, amount_minor, status,
expected_arrival_at, raw_payload_json; make settled_at nullable.

Revision ID: 0028_settlements
Revises: 83ca49021ddd
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_settlements"
down_revision = "83ca49021ddd"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to the existing settlements table (created in 0007)
    op.add_column("settlements", sa.Column("provider_account_id", sa.CHAR(36), nullable=True))
    op.add_column("settlements", sa.Column("amount_minor", sa.Integer(), nullable=True))
    op.add_column(
        "settlements",
        sa.Column("status", sa.String(32), server_default="pending", nullable=True),
    )
    op.add_column(
        "settlements",
        sa.Column("expected_arrival_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("settlements", sa.Column("raw_payload_json", sa.JSON(), nullable=True))

    # Allow settled_at to be NULL for pending settlements
    op.alter_column("settlements", "settled_at", nullable=True)

    # Backfill amount_minor from the existing amount column
    op.execute("UPDATE settlements SET amount_minor = amount WHERE amount_minor IS NULL")

    # Composite index requested by task spec
    op.create_index(
        "ix_settlements_merchant_provider",
        "settlements",
        ["merchant_id", "provider_name"],
    )


def downgrade():
    op.drop_index("ix_settlements_merchant_provider", table_name="settlements")
    op.alter_column("settlements", "settled_at", nullable=False)
    op.drop_column("settlements", "raw_payload_json")
    op.drop_column("settlements", "expected_arrival_at")
    op.drop_column("settlements", "status")
    op.drop_column("settlements", "amount_minor")
    op.drop_column("settlements", "provider_account_id")
