"""Add bank account last4 and data source provider account linkage

Revision ID: 0015_bank_account_last4_and_data_source_link
Revises: 0014_task001_foundation_hardening
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_bank_account_last4_and_data_source_link"
down_revision = "0014_task001_foundation_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bank_accounts") as batch_op:
        batch_op.add_column(sa.Column("account_number_last4", sa.String(length=4), nullable=True))

    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.add_column(sa.Column("provider_account_id", sa.CHAR(length=36), nullable=True))
        batch_op.create_index("ix_data_sources_provider_account_id", ["provider_account_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_data_sources_provider_account_id",
            "provider_accounts",
            ["provider_account_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.drop_constraint("fk_data_sources_provider_account_id", type_="foreignkey")
        batch_op.drop_index("ix_data_sources_provider_account_id")
        batch_op.drop_column("provider_account_id")

    with op.batch_alter_table("bank_accounts") as batch_op:
        batch_op.drop_column("account_number_last4")
