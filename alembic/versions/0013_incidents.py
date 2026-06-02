"""Add incidents and incident_events tables

Revision ID: 0013_incidents
Revises: 0012_provider_sync_jobs
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_incidents"
down_revision = "0012_provider_sync_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("merchant_id", sa.CHAR(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("incident_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("affected_amount_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.String(length=2048), nullable=False),
        sa.Column("ai_summary", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_merchant_id", "incidents", ["merchant_id"], unique=False)
    op.create_index("ix_incidents_merchant_status", "incidents", ["merchant_id", "status"], unique=False)
    op.create_index("ix_incidents_merchant_severity", "incidents", ["merchant_id", "severity"], unique=False)

    op.create_table(
        "incident_events",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("incident_id", sa.CHAR(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("message", sa.String(length=2048), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_incident_events_incident_id", table_name="incident_events")
    op.drop_table("incident_events")

    op.drop_index("ix_incidents_merchant_severity", table_name="incidents")
    op.drop_index("ix_incidents_merchant_status", table_name="incidents")
    op.drop_index("ix_incidents_merchant_id", table_name="incidents")
    op.drop_table("incidents")
