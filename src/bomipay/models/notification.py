import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, Integer, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class NotificationStatus(str, enum.Enum):
    unread = "unread"
    read = "read"
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    retry_scheduled = "retry_scheduled"
    abandoned = "abandoned"


class NotificationChannel(str, enum.Enum):
    in_app = "in_app"
    email = "email"
    sms = "sms"
    webhook = "webhook"


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    alert_id = Column(GUID(), ForeignKey("alerts.id"), nullable=True)
    channel = Column(String(32), nullable=False)
    message = Column(String(1024), nullable=False)
    status = Column(String(32), nullable=False, default=NotificationStatus.unread.value)
    delivery_key = Column(String(255), nullable=True, index=True)
    channel_message_id = Column(String(255), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    delivery_error = Column(String(1024), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    provider_response = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="notifications")
    merchant = relationship("Merchant")
    alert = relationship("Alert")
