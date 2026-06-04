import enum
import uuid
from sqlalchemy import Column, DateTime, Index, String, Text, func
from ..db import Base, GUID


class EventType(str, enum.Enum):
    transaction_created = "transaction.created"
    transaction_updated = "transaction.updated"
    transaction_settled = "transaction.settled"
    settlement_received = "settlement.received"
    settlement_mismatch_detected = "settlement.mismatch_detected"
    reconciliation_completed = "reconciliation.completed"
    reconciliation_mismatch = "reconciliation.mismatch"
    incident_created = "incident.created"
    incident_acknowledged = "incident.acknowledged"
    incident_resolved = "incident.resolved"
    alert_created = "alert.created"
    alert_resolved = "alert.resolved"
    dispute_created = "dispute.created"
    provider_sync_completed = "provider.sync.completed"
    provider_sync_failed = "provider.sync.failed"
    webhook_received = "webhook.received"
    webhook_processed = "webhook.processed"


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    merchant_id = Column(GUID(), nullable=False, index=True)
    aggregate_id = Column(String(255), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False)
    correlation_id = Column(String(36), nullable=True, index=True)
    request_id = Column(String(36), nullable=True)
    payload_json = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Composite index for efficient querying
    __table_args__ = (
        Index("idx_domain_events_merchant_type", "merchant_id", "event_type"),
        Index("idx_domain_events_aggregate", "aggregate_type", "aggregate_id"),
    )
