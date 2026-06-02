from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class IncidentCreate(BaseModel):
    merchant_id: Optional[str] = None
    title: str
    incident_type: str
    severity: str
    provider_name: Optional[str] = None
    affected_amount_minor: int = 0
    affected_transaction_count: int = 0
    started_at: datetime
    summary: str


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    severity: Optional[str] = None
    provider_name: Optional[str] = None
    affected_amount_minor: Optional[int] = None
    affected_transaction_count: Optional[int] = None
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    ai_summary: Optional[str] = None


class IncidentEventCreate(BaseModel):
    event_type: str
    message: str
    metadata_json: Optional[dict] = None


class IncidentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    incident_id: UUID | str
    event_type: str
    actor_user_id: Optional[UUID | str]
    message: str
    metadata_json: Optional[dict]
    created_at: datetime

    @field_serializer("id", "incident_id", "actor_user_id")
    def serialize_uuid(self, value: UUID | str | None, _info) -> Optional[str]:
        return str(value) if value else None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    merchant_id: UUID | str
    title: str
    incident_type: str
    severity: str
    status: str
    provider_name: Optional[str]
    affected_amount_minor: int
    affected_transaction_count: int
    started_at: datetime
    ended_at: Optional[datetime]
    summary: str
    ai_summary: Optional[str]
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "merchant_id")
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None
