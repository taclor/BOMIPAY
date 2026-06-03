import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class TransactionEvent(Base, TimestampMixin):
    __tablename__ = "transaction_events"
    __table_args__ = (
        UniqueConstraint("provider_name", "provider_event_id", name="uq_transaction_events_provider_event_id"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(GUID(), ForeignKey("transactions.id"), nullable=False)
    provider_name = Column(String(128), nullable=False)
    provider_event_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(128), nullable=False)
    provider_payload = Column(JSON, nullable=False)
    status = Column(String(32), nullable=True)

    transaction = relationship("Transaction", back_populates="events")
