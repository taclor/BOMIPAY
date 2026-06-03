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
    records_failed: int = 0
    error_message: Optional[str]
    error_severity: Optional[str]
    correlation_id: str
    created_at: datetime
    
    # Retry & backoff information
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    backoff_multiplier: float = 1.0
    failure_details: Optional[list] = None

    @field_serializer("id", "merchant_id", "provider_account_id")
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None

