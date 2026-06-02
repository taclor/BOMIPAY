from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, constr, field_serializer


class TransactionResponse(BaseModel):
    id: UUID | str
    merchant_id: UUID | str
    provider_name: str
    provider_transaction_id: str
    internal_reference: Optional[str]
    external_reference: Optional[str]
    payment_type: Optional[str]
    payment_channel: Optional[str]
    currency: str
    amount: int
    fee_amount: Optional[int]
    net_amount: Optional[int]
    status: str
    status_reason: Optional[str]
    initiated_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    settled_at: Optional[datetime]
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class TransactionEventResponse(BaseModel):
    id: UUID | str
    transaction_id: UUID | str
    provider_name: str
    provider_event_id: str
    event_type: str
    provider_payload: dict
    status: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'transaction_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class TransactionListQuery(BaseModel):
    status: Optional[constr(max_length=32)] = None
    provider_name: Optional[constr(max_length=128)] = None
    reference: Optional[constr(max_length=255)] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
