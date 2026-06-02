import enum
import uuid

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class MerchantStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    business_type = Column(String(128), nullable=True)
    email = Column(String(320), nullable=False)
    phone = Column(String(24), nullable=False)
    country = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default=MerchantStatus.active.value)
    is_kyc_ready = Column(Boolean, nullable=False, default=False)

    users = relationship("User", back_populates="merchant")
    provider_accounts = relationship("ProviderAccount", back_populates="merchant")
