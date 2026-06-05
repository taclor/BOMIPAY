import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.sql import func

from ..db import Base, GUID
from .base import TimestampMixin


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    provider_account_id = Column(GUID(), ForeignKey("provider_accounts.id"), nullable=True)
    provider_name = Column(String(128), nullable=False)
    settlement_reference = Column(String(255), nullable=False)
    # amount kept for backward-compatibility with rows written before 0028
    amount = Column(Integer, nullable=False)
    # canonical money field — never a float, always in smallest currency unit
    amount_minor = Column(Integer, nullable=True)
    currency = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending/settled/failed
    settled_at = Column(DateTime(timezone=True), nullable=True)
    expected_arrival_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)   # legacy
    raw_payload_json = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_settlements_merchant", "merchant_id"),
        Index("ix_settlements_reference", "settlement_reference"),
        Index("ix_settlements_merchant_provider", "merchant_id", "provider_name"),
    )
