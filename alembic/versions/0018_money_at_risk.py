"""Add money_at_risk table

Revision ID: 0018_money_at_risk
Revises: 0017_provider_sync_enhancements
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_money_at_risk"
down_revision = "0017_provider_sync_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "money_at_risk",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("pending_transactions_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("pending_transactions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unreconciled_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("unreconciled_transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_transfers_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("failed_transfers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_at_risk", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breakdown_by_provider", sa.JSON(), nullable=True),
        sa.Column("breakdown_by_status", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_money_at_risk_merchant_id", "money_at_risk", ["merchant_id"], unique=False)
    op.create_index("ix_money_at_risk_merchant_period", "money_at_risk", ["merchant_id", "period_date"], unique=True)
    op.create_index("ix_money_at_risk_period_date", "money_at_risk", ["period_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_money_at_risk_period_date", table_name="money_at_risk")
    op.drop_index("ix_money_at_risk_merchant_period", table_name="money_at_risk")
    op.drop_index("ix_money_at_risk_merchant_id", table_name="money_at_risk")
    op.drop_table("money_at_risk")
