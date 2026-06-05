"""Make phone nullable and fix settlements UUID columns

Revision ID: 0029_phone_nullable_settlements_uuid
Revises: 0028_settlements
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029_phone_nullable_settlements_uuid"
down_revision = "0028_settlements"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "phone", existing_type=sa.String(24), nullable=True)
    op.alter_column("merchants", "phone", existing_type=sa.String(24), nullable=True)
    # Fix settlements UUID types if they were created as CHAR
    op.execute("ALTER TABLE settlements ALTER COLUMN id TYPE uuid USING id::uuid")
    op.execute("ALTER TABLE settlements ALTER COLUMN merchant_id TYPE uuid USING merchant_id::uuid")


def downgrade():
    op.alter_column("users", "phone", existing_type=sa.String(24), nullable=False)
    op.alter_column("merchants", "phone", existing_type=sa.String(24), nullable=False)
