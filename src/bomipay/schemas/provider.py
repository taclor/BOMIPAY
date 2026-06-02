from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, constr


class ProviderCredentials(BaseModel):
    api_key: constr(min_length=1)
    secret_key: constr(min_length=1)


class ProviderConnectRequest(BaseModel):
    merchant_id: Optional[str]
    provider_name: constr(min_length=2, max_length=128)
    credentials: ProviderCredentials


class ProviderAccountData(BaseModel):
    provider_account_id: UUID | str
    provider_name: str
    status: str


class ProviderConnectResponse(BaseModel):
    success: bool
    data: ProviderAccountData


class ProviderHealthResponse(BaseModel):
    provider_name: str
    merchant_id: UUID | str
    status: str
    connected: bool


class ProviderListResponse(BaseModel):
    provider_account_id: UUID | str
    provider_name: str
    merchant_id: UUID | str
    status: str

    model_config = ConfigDict(from_attributes=True)
