from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ExpectedPaymentImportItem(BaseModel):
    reference: str
    amount: int
    currency: str
    due_date: datetime
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ExpectedPaymentResponse(BaseModel):
    id: UUID | str
    merchant_id: UUID | str
    reference: str
    amount: int
    currency: str
    due_date: datetime
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]
    status: str
    metadata_json: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRunCreateRequest(BaseModel):
    date_from: datetime
    date_to: datetime
    run_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReconciliationResultResponse(BaseModel):
    id: UUID | str
    run_id: UUID | str
    expected_payment_id: UUID | str
    transaction_id: Optional[UUID | str]
    match_status: str
    confidence_score: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRunResponse(BaseModel):
    id: UUID | str
    merchant_id: UUID | str
    run_name: Optional[str]
    date_from: datetime
    date_to: datetime
    matching_policy_version: str
    source_expected_payment_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationSummaryResponse(BaseModel):
    run_id: UUID | str
    merchant_id: UUID | str
    run_name: Optional[str]
    status: str
    date_from: datetime
    date_to: datetime
    expected_count: int
    matched_count: int
    partial_count: int
    unmatched_count: int
    duplicate_count: int
    total_expected_amount: int
    total_matched_amount: int

    model_config = ConfigDict(from_attributes=True)


class ExpectedPaymentImportResponse(BaseModel):
    rows_received: int
    rows_inserted: int
    rows_skipped: int
    rows_rejected: int
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)
