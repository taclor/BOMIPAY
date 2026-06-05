from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, constr, field_serializer


class ProviderCredentials(BaseModel):
    api_key: constr(min_length=1)
    secret_key: constr(min_length=1)


class ProviderConnectRequest(BaseModel):
    merchant_id: Optional[str]
    provider_name: constr(min_length=2, max_length=128)
    credentials: ProviderCredentials


class ProviderTestRequest(BaseModel):
    provider_name: constr(min_length=2, max_length=128)
    public_key: constr(min_length=1)
    secret_key: constr(min_length=1)
    webhook_secret: Optional[str] = None


class ProviderTestResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class ProviderAccountData(BaseModel):
    provider_account_id: UUID | str
    provider_name: str
    status: str

    @field_serializer('provider_account_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class ProviderConnectResponse(BaseModel):
    success: bool
    data: ProviderAccountData


class ProviderHealthResponse(BaseModel):
    provider_name: str
    merchant_id: UUID | str
    status: str
    connected: bool

    @field_serializer('merchant_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class ProviderListResponse(BaseModel):
    provider_account_id: UUID | str
    provider_name: str
    merchant_id: UUID | str
    status: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('provider_account_id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None
