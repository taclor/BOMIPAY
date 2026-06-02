import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class IncidentType(str, enum.Enum):
    provider_failure_spike = "provider_failure_spike"
    settlement_delay = "settlement_delay"
    webhook_failure = "webhook_failure"
    reconciliation_mismatch = "reconciliation_mismatch"
    duplicate_payment_risk = "duplicate_payment_risk"
    hanging_transaction = "hanging_transaction"
    bank_statement_mismatch = "bank_statement_mismatch"


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    investigating = "investigating"
    resolved = "resolved"
    closed = "closed"


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    incident_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default=IncidentStatus.open.value)
    provider_name = Column(String(128), nullable=True)
    affected_amount_minor = Column(Integer, nullable=False, default=0)
    affected_transaction_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    summary = Column(String(2048), nullable=False)
    ai_summary = Column(String(4096), nullable=True)

    merchant = relationship("Merchant")
    incident_events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id"), nullable=False, index=True)
    event_type = Column(String(128), nullable=False)
    actor_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    message = Column(String(2048), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    incident = relationship("Incident", back_populates="incident_events")
