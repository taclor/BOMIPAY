"""add alert fields rule_code source_type acknowledged_at resolved_at occurrence_count

Revision ID: 0008
Revises: 0007_reconciliation_engine
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007_reconciliation_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("alerts")}

    if "source_type" not in existing_columns:
        op.add_column("alerts", sa.Column("source_type", sa.String(64), nullable=True))
    if "rule_code" not in existing_columns:
        op.add_column("alerts", sa.Column("rule_code", sa.String(128), nullable=True))
    if "occurrence_count" not in existing_columns:
        op.add_column("alerts", sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"))
    if "acknowledged_at" not in existing_columns:
        op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    if "resolved_at" not in existing_columns:
        op.add_column("alerts", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # No-op: these columns are managed by earlier migrations in the linear chain.
    pass
