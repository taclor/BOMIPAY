import enum
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class MoneyAtRiskStatus(str, enum.Enum):
    """Status of a money-at-risk snapshot."""
    active = "active"
    resolved = "resolved"
    archived = "archived"


class MoneyAtRisk(Base, TimestampMixin):
    """Daily Money-at-Risk (MAR) snapshot tracking financial exposure.
    
    Tracks pending transactions, unreconciled funds, and failed transfers
    to measure financial exposure for a merchant on a given date.
    """
    __tablename__ = "money_at_risk"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    period_date = Column(Date(), nullable=False, index=True)
    
    # Pending transactions (status=pending AND age >= 30 minutes)
    pending_transactions_amount = Column(Numeric(18, 2), nullable=False, default=0)
    pending_transactions_count = Column(Integer(), nullable=False, default=0)
    
    # Unreconciled funds (unmatched transactions AND age >= 7 days)
    unreconciled_amount = Column(Numeric(18, 2), nullable=False, default=0)
    unreconciled_transaction_count = Column(Integer(), nullable=False, default=0)
    
    # Failed transfers (status=failed AND age >= 1 day)
    failed_transfers_amount = Column(Numeric(18, 2), nullable=False, default=0)
    failed_transfers_count = Column(Integer(), nullable=False, default=0)
    
    # Computed: sum of above three categories
    total_at_risk = Column(Numeric(18, 2), nullable=False, default=0)
    
    # Risk score 0-100 based on aging and volume
    risk_score = Column(Integer(), nullable=False, default=0)
    
    # Breakdown by provider {provider_name: {amount, count}}
    breakdown_by_provider = Column(JSON(), nullable=True, default=dict)
    
    # Breakdown by status {status: {amount, count}}
    breakdown_by_status = Column(JSON(), nullable=True, default=dict)
    
    # Indexes for common queries
    __table_args__ = (
        # Composite indexes for common filtering patterns
        # Efficiently find current MAR snapshot
    )
