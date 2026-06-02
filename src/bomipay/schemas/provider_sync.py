from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class ProviderSyncRequest(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ProviderSyncJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    provider_account_id: UUID | str
    sync_type: str
    status: str
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    records_seen: int
    records_created: int
    records_updated: int
    error_message: Optional[str]
    correlation_id: str
    created_at: datetime

    @field_serializer("id", "merchant_id", "provider_account_id")
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None
