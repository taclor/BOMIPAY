from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class BankStatementImportCreate(BaseModel):
    merchant_id: Optional[str] = None
    bank_account_id: Optional[str] = None
    file_name: str
    file_type: str
    rows_data: list[dict]


class BankStatementImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    bank_account_id: Optional[UUID | str]
    file_name: str
    file_type: str
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_summary: Optional[Any]
    completed_at: Optional[datetime]
    created_at: datetime

    @field_serializer("id", "merchant_id", "bank_account_id")
    def serialize_uuid(self, value: UUID | str | None, _info) -> Optional[str]:
        return str(value) if value else None


class BankStatementEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    import_id: UUID | str
    bank_account_id: Optional[UUID | str]
    entry_date: datetime
    value_date: Optional[datetime]
    description: str
    reference: Optional[str]
    debit_amount_minor: int
    credit_amount_minor: int
    currency: str
    balance_after_minor: Optional[int]
    counterparty_name: Optional[str]
    created_at: datetime

    @field_serializer("id", "merchant_id", "import_id", "bank_account_id")
    def serialize_uuid(self, value: UUID | str | None, _info) -> Optional[str]:
        return str(value) if value else None
