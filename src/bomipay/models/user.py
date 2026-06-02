import enum
import uuid

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class Role(str, enum.Enum):
    admin = "admin"
    merchant_user = "merchant_user"
    finance = "finance"
    support = "support"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(320), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(24), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default=UserStatus.active.value)
    role = Column(Enum(Role), nullable=False, default=Role.merchant_user)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=True)

    merchant = relationship("Merchant", back_populates="users")
    notifications = relationship("Notification", back_populates="user")
