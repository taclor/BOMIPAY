from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, constr


class AlertResponse(BaseModel):
    id: UUID | str
    merchant_id: UUID | str
    transaction_id: Optional[UUID | str]
    source_event_id: Optional[str]
    source_type: Optional[str]
    rule_code: Optional[str]
    alert_type: str
    severity: str
    status: str
    description: str
    metadata_json: Optional[dict]
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListQuery(BaseModel):
    status: Optional[constr(max_length=32)] = None
    severity: Optional[constr(max_length=32)] = None
    alert_type: Optional[constr(max_length=64)] = None


class AlertActionRequest(BaseModel):
    status: constr(min_length=1, max_length=32)
