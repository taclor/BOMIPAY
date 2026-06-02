import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from .base import TimestampMixin
from ..db import Base, GUID


class ProviderSyncType(str, enum.Enum):
    transactions = "transactions"
    settlements = "settlements"
    transfers = "transfers"
    refunds = "refunds"
    provider_health = "provider_health"


class ProviderSyncStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProviderSyncJob(Base, TimestampMixin):
    __tablename__ = "provider_sync_jobs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    provider_account_id = Column(GUID(), ForeignKey("provider_accounts.id"), nullable=False, index=True)
    sync_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default=ProviderSyncStatus.queued.value)
    date_from = Column(DateTime(timezone=True), nullable=True)
    date_to = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    records_seen = Column(Integer, nullable=False, default=0)
    records_created = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    error_message = Column(String(1024), nullable=True)
    correlation_id = Column(String(255), nullable=False, index=True)
    raw_response_json = Column(JSON, nullable=True)
