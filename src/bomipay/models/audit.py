import uuid

from sqlalchemy import Column, ForeignKey, JSON, String

from .base import TimestampMixin
from ..db import Base, GUID


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    actor_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(64), nullable=True)
    event_type = Column(String(128), nullable=False)
    event_payload = Column(JSON, nullable=True)
    source = Column(String(64), nullable=False, default="api")
