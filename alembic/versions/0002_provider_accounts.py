"""Add provider account table

Revision ID: 0002_provider_accounts
Revises: 0001_initial
Create Date: 2026-04-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_provider_accounts"
down_revision = "0001_initial"
branch_labels = None
depend_on = None


def upgrade() -> None:
    op.create_table(
        "provider_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("secret_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_accounts")
