from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, constr, field_serializer


class NotificationResponse(BaseModel):
    id: UUID | str
    user_id: Optional[UUID | str]
    merchant_id: UUID | str
    alert_id: Optional[UUID | str]
    channel: str
    message: str
    status: str
    delivery_error: Optional[str]
    retry_count: int
    provider_response: Optional[dict]
    metadata_json: Optional[dict]
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'user_id', 'merchant_id', 'alert_id')
    def serialize_uuid(self, value: UUID | str | None, _info) -> str | None:
        return str(value) if value else None


class NotificationListQuery(BaseModel):
    user_id: Optional[constr(min_length=1)] = None
    status: Optional[constr(min_length=1, max_length=32)] = None
