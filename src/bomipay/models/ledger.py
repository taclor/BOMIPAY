import enum
import uuid

from sqlalchemy import Boolean, Column, String, BigInteger, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class LedgerAccount(Base, TimestampMixin):
    """Immutable ledger account - one per merchant + account_code combination."""
    __tablename__ = "ledger_accounts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    account_code = Column(String(64), nullable=False)  # e.g., "MAIN", "FEE_PAYABLE", "SETTLEMENT"
    is_active = Column(Boolean, nullable=False, default=True)

    journal_entries = relationship("JournalEntry", back_populates="account")

    __table_args__ = (
        Index("ix_ledger_accounts_merchant_id", "merchant_id"),
        Index("ix_ledger_accounts_merchant_account_code", "merchant_id", "account_code", unique=True),
    )


class JournalEntry(Base, TimestampMixin):
    """Append-only journal entry. Double-entry bookkeeping requires balanced lines."""
    __tablename__ = "journal_entries"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    account_id = Column(GUID(), ForeignKey("ledger_accounts.id"), nullable=False)
    
    # Idempotency: if same key posted, returns existing entry without duplicating
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    
    description = Column(String(512), nullable=False)
    transaction_id = Column(GUID(), nullable=True)  # Reference to originating transaction
    
    ledger_lines = relationship("LedgerLine", back_populates="journal_entry", cascade="all, delete-orphan")
    account = relationship("LedgerAccount", back_populates="journal_entries")

    __table_args__ = (
        Index("ix_journal_entries_merchant_id", "merchant_id"),
        Index("ix_journal_entries_account_id", "account_id"),
        Index("ix_journal_entries_transaction_id", "transaction_id"),
    )


class LedgerLine(Base, TimestampMixin):
    """Immutable ledger line - part of a journal entry. Debit or credit."""
    __tablename__ = "ledger_lines"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    journal_entry_id = Column(GUID(), ForeignKey("journal_entries.id"), nullable=False)
    account_code = Column(String(64), nullable=False)  # Which account this line affects
    
    # Amount in minor units (cents/satoshis). Always positive, debit/credit determined by line_type
    amount_minor = Column(BigInteger, nullable=False)
    line_type = Column(String(16), nullable=False)  # "DEBIT" or "CREDIT"
    
    description = Column(String(512), nullable=True)
    
    journal_entry = relationship("JournalEntry", back_populates="ledger_lines")

    __table_args__ = (
        Index("ix_ledger_lines_journal_entry_id", "journal_entry_id"),
        CheckConstraint("amount_minor > 0", name="check_ledger_lines_amount_positive"),
        CheckConstraint("line_type IN ('DEBIT', 'CREDIT')", name="check_ledger_lines_type"),
    )


class FeeRecord(Base, TimestampMixin):
    """Immutable fee tracking for audit trail."""
    __tablename__ = "fee_records"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False)
    journal_entry_id = Column(GUID(), ForeignKey("journal_entries.id"), nullable=False)
    
    fee_type = Column(String(64), nullable=False)  # e.g., "TRANSACTION_FEE", "SETTLEMENT_FEE"
    amount_minor = Column(BigInteger, nullable=False)  # Fee amount in minor units
    description = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_fee_records_merchant_id", "merchant_id"),
        Index("ix_fee_records_journal_entry_id", "journal_entry_id"),
        CheckConstraint("amount_minor > 0", name="check_fee_records_amount_positive"),
    )
