import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class BankStatementFileType(str, enum.Enum):
    csv = "csv"
    xlsx = "xlsx"


class BankStatementImportStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class BankStatementImport(Base, TimestampMixin):
    __tablename__ = "bank_statement_imports"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    bank_account_id = Column(GUID(), ForeignKey("bank_accounts.id"), nullable=True, index=True)
    file_name = Column(String(512), nullable=False)
    file_type = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default=BankStatementImportStatus.uploaded.value)
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)
    error_summary = Column(JSON, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    merchant = relationship("Merchant")
    bank_account = relationship("BankAccount")
    entries = relationship("BankStatementEntry", back_populates="import_record", cascade="all, delete-orphan")


class BankStatementEntry(Base):
    __tablename__ = "bank_statement_entries"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    import_id = Column(GUID(), ForeignKey("bank_statement_imports.id"), nullable=False, index=True)
    bank_account_id = Column(GUID(), ForeignKey("bank_accounts.id"), nullable=True, index=True)
    entry_date = Column(DateTime(timezone=True), nullable=False, index=True)
    value_date = Column(DateTime(timezone=True), nullable=True)
    description = Column(String(1024), nullable=False)
    reference = Column(String(255), nullable=True, index=True)
    debit_amount_minor = Column(Integer, nullable=False, default=0)
    credit_amount_minor = Column(Integer, nullable=False, default=0)
    currency = Column(String(16), nullable=False)
    balance_after_minor = Column(Integer, nullable=True)
    counterparty_name = Column(String(255), nullable=True)
    raw_row_json = Column(JSON, nullable=True)
    normalized_hash = Column(String(128), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    merchant = relationship("Merchant")
    bank_account = relationship("BankAccount")
    import_record = relationship("BankStatementImport", back_populates="entries")
