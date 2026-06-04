"""Provider sync checkpoint model for tracking pagination state."""
import uuid

from sqlalchemy import Column, ForeignKey, Integer, String

from .base import TimestampMixin
from ..db import Base, GUID


class ProviderSyncCheckpoint(Base, TimestampMixin):
    """Track where we left off in provider pagination."""

    __tablename__ = "provider_sync_checkpoints"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    provider_account_id = Column(
        GUID(), ForeignKey("provider_accounts.id"), nullable=False, index=True
    )
    sync_type = Column(String(50), nullable=False)  # transactions, settlements, transfers, refunds
    last_synced_timestamp = Column(
        String(255), nullable=True
    )  # ISO format of last transaction timestamp we saw
    last_page_cursor = Column(String(255), nullable=True)  # Pagination cursor from provider
    checkpoint_version = Column(Integer, nullable=False, default=1)  # For future format changes
