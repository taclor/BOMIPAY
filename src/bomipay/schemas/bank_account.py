from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class BankAccountCreate(BaseModel):
    merchant_id: Optional[str] = None
    bank_name: str
    bank_code: Optional[str] = None
    account_number: str
    account_name: str
    currency: str = "NGN"
    purpose: str = "settlement"
    metadata_json: Optional[dict] = None


class BankAccountUpdate(BaseModel):
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    account_name: Optional[str] = None
    currency: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[str] = None
    metadata_json: Optional[dict] = None


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    bank_name: str
    bank_code: Optional[str]
    account_number_masked: str
    account_name: str
    currency: str
    purpose: str
    verification_status: str
    status: str
    metadata_json: Optional[dict]

    @field_serializer("id", "merchant_id")
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class BankAccountVerifyResponse(BaseModel):
    bank_account_id: str
    verification_status: str
    message: str


class BankAccountListResponse(BaseModel):
    items: list[BankAccountResponse]
    total: int
