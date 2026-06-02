import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class DataSourceType(str, enum.Enum):
    provider_api = "provider_api"
    provider_webhook = "provider_webhook"
    bank_statement_upload = "bank_statement_upload"
    csv_upload = "csv_upload"
    erp_export = "erp_export"
    pos_export = "pos_export"
    manual_entry = "manual_entry"


class DataSourceStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"
    pending_setup = "pending_setup"


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    source_type = Column(String(64), nullable=False)
    provider_name = Column(String(128), nullable=True)
    display_name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default=DataSourceStatus.pending_setup.value)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    last_error_message = Column(String(1024), nullable=True)
    configuration_json = Column(JSON, nullable=True)

    merchant = relationship("Merchant")
