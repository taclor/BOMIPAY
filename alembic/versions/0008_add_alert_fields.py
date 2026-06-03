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
    # Add new columns to alerts table
    op.add_column('alerts', sa.Column('source_type', sa.String(64), nullable=True))
    op.add_column('alerts', sa.Column('rule_code', sa.String(128), nullable=True))
    op.add_column('alerts', sa.Column('occurrence_count', sa.Integer, nullable=False, server_default='1'))
    op.add_column('alerts', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from alerts table
    op.drop_column('alerts', 'resolved_at')
    op.drop_column('alerts', 'acknowledged_at')
    op.drop_column('alerts', 'occurrence_count')
    op.drop_column('alerts', 'rule_code')
    op.drop_column('alerts', 'source_type')
