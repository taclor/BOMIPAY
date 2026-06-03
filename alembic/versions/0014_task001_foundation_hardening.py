"""Task 001 foundation hardening

Revision ID: 0014_task001_foundation_hardening
Revises: 0013_incidents
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_task001_foundation_hardening"
down_revision = "0013_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transaction_events") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transaction_events_provider_event_id",
            ["provider_name", "provider_event_id"],
        )

    with op.batch_alter_table("reconciliation_results") as batch_op:
        batch_op.alter_column(
            "confidence_score",
            new_column_name="confidence_score_bps",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text("0.0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("reconciliation_results") as batch_op:
        batch_op.alter_column(
            "confidence_score_bps",
            new_column_name="confidence_score",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )

    with op.batch_alter_table("transaction_events") as batch_op:
        batch_op.drop_constraint("uq_transaction_events_provider_event_id", type_="unique")