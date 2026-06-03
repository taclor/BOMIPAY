import enum
import uuid

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .audit import AuditLog
from .base import TimestampMixin
from ..db import Base, GUID


class ExpectedPaymentStatus(str, enum.Enum):
    pending = "pending"
    matched = "matched"
    reconciled = "reconciled"
    canceled = "canceled"


class ReconciliationRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReconciliationMatchStatus(str, enum.Enum):
    matched = "matched"
    weak = "weak"
    unmatched = "unmatched"
    duplicate = "duplicate"
    underpaid = "underpaid"
    overpaid = "overpaid"
    ambiguous = "ambiguous"


class ExpectedPaymentImportBatch(Base, TimestampMixin):
    __tablename__ = "expected_payment_import_batches"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=True)
    file_hash = Column(String(128), nullable=True)
    rows_received = Column(Integer, nullable=False, default=0)
    rows_inserted = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    rows_rejected = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSON, nullable=True)

    expected_payments = relationship("ExpectedPayment", back_populates="import_batch")


class ExpectedPayment(Base, TimestampMixin):
    __tablename__ = "expected_payments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    import_batch_id = Column(GUID(), ForeignKey("expected_payment_import_batches.id"), nullable=True, index=True)
    reference = Column(String(255), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(320), nullable=True)
    customer_phone = Column(String(24), nullable=True)
    status = Column(Enum(ExpectedPaymentStatus), nullable=False, default=ExpectedPaymentStatus.pending)
    metadata_json = Column(JSON, nullable=True)

    import_batch = relationship("ExpectedPaymentImportBatch", back_populates="expected_payments")
    reconciliation_results = relationship("ReconciliationResult", back_populates="expected_payment")


class ReconciliationRun(Base, TimestampMixin):
    __tablename__ = "reconciliation_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    run_name = Column(String(255), nullable=True)
    date_from = Column(DateTime(timezone=True), nullable=False)
    date_to = Column(DateTime(timezone=True), nullable=False)
    matching_policy_version = Column(String(32), nullable=False, default="1.0")
    source_expected_payment_count = Column(Integer, nullable=False, default=0)
    status = Column(Enum(ReconciliationRunStatus), nullable=False, default=ReconciliationRunStatus.pending)

    results = relationship("ReconciliationResult", back_populates="reconciliation_run")


class ReconciliationResult(Base, TimestampMixin):
    __tablename__ = "reconciliation_results"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    run_id = Column(GUID(), ForeignKey("reconciliation_runs.id"), nullable=False, index=True)
    expected_payment_id = Column(GUID(), ForeignKey("expected_payments.id"), nullable=False, index=True)
    transaction_id = Column(GUID(), ForeignKey("transactions.id"), nullable=True, index=True)
    match_status = Column(Enum(ReconciliationMatchStatus), nullable=False)
    confidence_score_bps = Column(Integer, nullable=False, default=0)
    notes = Column(String(1024), nullable=True)

    reconciliation_run = relationship("ReconciliationRun", back_populates="results")
    expected_payment = relationship("ExpectedPayment", back_populates="reconciliation_results")
    transaction = relationship("Transaction")


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    provider_name = Column(String(128), nullable=False)
    settlement_reference = Column(String(255), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False)
    settled_at = Column(DateTime(timezone=True), nullable=False)
    metadata_json = Column(JSON, nullable=True)
