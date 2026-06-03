from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class DataSourceCreate(BaseModel):
    merchant_id: Optional[str] = None
    source_type: str
    provider_name: Optional[str] = None
    provider_account_id: Optional[str] = None
    display_name: str
    configuration_json: Optional[dict] = None


class DataSourceUpdate(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None
    configuration_json: Optional[dict] = None
    provider_name: Optional[str] = None
    provider_account_id: Optional[str] = None


class DataSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    source_type: str
    provider_name: Optional[str]
    provider_account_id: Optional[UUID | str]
    display_name: str
    status: str
    last_sync_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error_at: Optional[datetime]
    last_error_message: Optional[str]
    configuration_json: Optional[dict]

    @field_serializer("id", "merchant_id", "provider_account_id")
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class DataSourceTestResponse(BaseModel):
    data_source_id: str
    success: bool
    message: str
    details: Optional[dict] = None


class DataSourceSyncStatus(BaseModel):
    data_source_id: str
    status: str
    last_sync_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error_at: Optional[datetime]
    last_error_message: Optional[str]
    health: str
