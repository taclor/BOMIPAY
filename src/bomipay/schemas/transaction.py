from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, constr


class TransactionResponse(BaseModel):
    id: str
    merchant_id: str
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


class TransactionListQuery(BaseModel):
    status: Optional[constr(max_length=32)] = None
    provider_name: Optional[constr(max_length=128)] = None
    reference: Optional[constr(max_length=255)] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
