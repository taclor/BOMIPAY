import enum
import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class ProviderAccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class ProviderAccount(Base, TimestampMixin):
    __tablename__ = "provider_accounts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    provider_name = Column(String(128), nullable=False)
    api_key_encrypted = Column(String(1024), nullable=False)
    secret_encrypted = Column(String(1024), nullable=False)
    status = Column(String(32), nullable=False, default=ProviderAccountStatus.active.value)

    merchant = relationship("Merchant", back_populates="provider_accounts")
