"""Add AI Prompt Versioning and Response Logging

Revision ID: 0025_ai_prompt_versioning
Revises: 0024_provider_health
Create Date: 2024-01-17 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "0025_ai_prompt_versioning"
down_revision = "0024_provider_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ai_prompt_versions table
    op.create_table(
        "ai_prompt_versions",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("retrieval_sources", sa.JSON(), nullable=False),
        sa.Column("safety_flags", sa.JSON(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("version"),
    )

    # Create ai_response_logs table
    op.create_table(
        "ai_response_logs",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("context_sources", sa.JSON(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("has_hallucinations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cited_record_ids", sa.JSON(), nullable=False),
        sa.Column("retrieval_query", sa.Text(), nullable=True),
        sa.Column("response_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_version"], ["ai_prompt_versions.version"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_ai_response_logs_merchant_id",
        "ai_response_logs",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_response_logs_prompt_version",
        "ai_response_logs",
        ["prompt_version"],
        unique=False,
    )
    op.create_index(
        "ix_ai_response_logs_created_at",
        "ai_response_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_response_logs_merchant_created",
        "ai_response_logs",
        ["merchant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_response_logs_merchant_created", table_name="ai_response_logs")
    op.drop_index("ix_ai_response_logs_created_at", table_name="ai_response_logs")
    op.drop_index("ix_ai_response_logs_prompt_version", table_name="ai_response_logs")
    op.drop_index("ix_ai_response_logs_merchant_id", table_name="ai_response_logs")
    op.drop_table("ai_response_logs")
    op.drop_table("ai_prompt_versions")
