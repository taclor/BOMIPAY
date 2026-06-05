from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class SettlementResponse(BaseModel):
    id: UUID
    merchant_id: UUID
    provider_account_id: Optional[UUID] = None
    provider_name: str
    settlement_reference: str
    amount_minor: Optional[int] = None
    currency: str
    status: str
    settled_at: Optional[datetime] = None
    expected_arrival_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementSummaryResponse(BaseModel):
    total_settled: int
    total_pending: int
    by_currency_status: List[Dict[str, Any]]
