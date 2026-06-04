"""Add AI Token Usage Tracking

Revision ID: 0026_ai_token_usage
Revises: 0025_ai_prompt_versioning
Create Date: 2024-01-17 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "0026_ai_token_usage"
down_revision = "0025_ai_prompt_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ai_token_usage table
    op.create_table(
        "ai_token_usage",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("ai_response_log_id", sa.CHAR(length=36), nullable=False),
        sa.Column("query_tokens", sa.Integer(), nullable=False),
        sa.Column("response_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_ai_token_usage_merchant_id",
        "ai_token_usage",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_token_usage_ai_response_log_id",
        "ai_token_usage",
        ["ai_response_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_token_usage_created_at",
        "ai_token_usage",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_token_usage_merchant_created",
        "ai_token_usage",
        ["merchant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_token_usage_merchant_created", table_name="ai_token_usage")
    op.drop_index("ix_ai_token_usage_created_at", table_name="ai_token_usage")
    op.drop_index("ix_ai_token_usage_ai_response_log_id", table_name="ai_token_usage")
    op.drop_index("ix_ai_token_usage_merchant_id", table_name="ai_token_usage")
    op.drop_table("ai_token_usage")
