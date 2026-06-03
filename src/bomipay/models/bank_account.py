import enum
import uuid

from sqlalchemy import Column, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class BankAccountPurpose(str, enum.Enum):
    settlement = "settlement"
    operations = "operations"
    payout = "payout"
    reconciliation = "reconciliation"


class BankAccountVerificationStatus(str, enum.Enum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    failed = "failed"


class BankAccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    bank_name = Column(String(255), nullable=False)
    bank_code = Column(String(64), nullable=True)
    account_number_encrypted = Column(String(1024), nullable=False)
    account_number_last4 = Column(String(4), nullable=False)
    account_name = Column(String(255), nullable=False)
    currency = Column(String(16), nullable=False, default="NGN")
    purpose = Column(String(32), nullable=False, default=BankAccountPurpose.settlement.value)
    verification_status = Column(
        String(32), nullable=False, default=BankAccountVerificationStatus.unverified.value
    )
    status = Column(String(32), nullable=False, default=BankAccountStatus.active.value)
    metadata_json = Column(JSON, nullable=True)

    merchant = relationship("Merchant")
