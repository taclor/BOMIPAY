"""Add domain_events table for event bus.

Revision ID: 0023_domain_events
Revises: 0020_provider_sync_checkpoints
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0023_domain_events'
down_revision = '0020_provider_sync_checkpoints'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'domain_events',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('merchant_id', sa.CHAR(36), nullable=False),
        sa.Column('aggregate_id', sa.String(255), nullable=False),
        sa.Column('aggregate_type', sa.String(50), nullable=False),
        sa.Column('correlation_id', sa.String(36), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('payload_json', sa.Text, nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('idx_domain_events_event_type', 'domain_events', ['event_type'])
    op.create_index('idx_domain_events_merchant_id', 'domain_events', ['merchant_id'])
    op.create_index('idx_domain_events_aggregate_id', 'domain_events', ['aggregate_id'])
    op.create_index('idx_domain_events_correlation_id', 'domain_events', ['correlation_id'])
    op.create_index('idx_domain_events_published_at', 'domain_events', ['published_at'])
    op.create_index('idx_domain_events_merchant_type', 'domain_events', ['merchant_id', 'event_type'])
    op.create_index('idx_domain_events_aggregate', 'domain_events', ['aggregate_type', 'aggregate_id'])


def downgrade() -> None:
    op.drop_index('idx_domain_events_aggregate')
    op.drop_index('idx_domain_events_merchant_type')
    op.drop_index('idx_domain_events_published_at')
    op.drop_index('idx_domain_events_correlation_id')
    op.drop_index('idx_domain_events_aggregate_id')
    op.drop_index('idx_domain_events_merchant_id')
    op.drop_index('idx_domain_events_event_type')
    op.drop_table('domain_events')
