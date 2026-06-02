import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Integer

from .base import TimestampMixin
from ..db import Base, GUID


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class AlertType(str, enum.Enum):
    transaction_failure = "transaction_failure"
    hanging_payment = "hanging_payment"
    reconciliation_mismatch = "reconciliation_mismatch"
    provider_error = "provider_error"


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    transaction_id = Column(GUID(), ForeignKey("transactions.id"), nullable=True)
    source_event_id = Column(String(255), nullable=True)
    source_type = Column(String(64), nullable=True)
    rule_code = Column(String(128), nullable=True)
    alert_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default=AlertStatus.open.value)
    description = Column(String(1024), nullable=False)
    occurrence_count = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSON, nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

