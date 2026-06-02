import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    settled = "settled"
    canceled = "canceled"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    provider_name = Column(String(128), nullable=False)
    provider_transaction_id = Column(String(255), nullable=False, index=True)
    internal_reference = Column(String(255), nullable=True, index=True)
    external_reference = Column(String(255), nullable=True, index=True)
    payment_type = Column(String(64), nullable=True)
    payment_channel = Column(String(64), nullable=True)
    currency = Column(String(16), nullable=False)
    amount = Column(Integer, nullable=False)
    fee_amount = Column(Integer, nullable=True, default=0)
    net_amount = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default=TransactionStatus.pending.value)
    status_reason = Column(String(255), nullable=True)
    initiated_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(320), nullable=True)
    customer_phone = Column(String(24), nullable=True)
    metadata_json = Column(JSON, nullable=True)

    events = relationship("TransactionEvent", back_populates="transaction", cascade="all, delete-orphan")
