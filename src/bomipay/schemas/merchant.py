from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, constr, field_serializer

from ..models.user import Role


class MerchantResponse(BaseModel):
    id: UUID | str
    name: str
    business_type: Optional[str]
    email: str
    phone: str
    country: Optional[str]
    status: str
    is_kyc_ready: bool

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None


class MerchantCreateRequest(BaseModel):
    name: constr(min_length=2, max_length=255)
    email: EmailStr
    phone: constr(min_length=10, max_length=24)
    business_type: Optional[constr(max_length=128)] = None
    country: Optional[constr(max_length=64)] = None


class MerchantMemberCreateRequest(BaseModel):
    full_name: constr(min_length=2, max_length=255)
    email: EmailStr
    phone: constr(min_length=10, max_length=24)
    password: constr(min_length=12)
    role: Role = Role.merchant_user


class UpdateMerchantRequest(BaseModel):
    name: Optional[constr(min_length=2, max_length=255)] = None
    business_type: Optional[constr(max_length=128)] = None
    email: Optional[constr(max_length=320)] = None
    phone: Optional[constr(min_length=10, max_length=24)] = None
    country: Optional[constr(max_length=64)] = None
    is_kyc_ready: Optional[bool] = None


class ProviderAccountCreateRequest(BaseModel):
    provider_name: constr(min_length=2, max_length=128)
    api_key: constr(min_length=1)
    secret: constr(min_length=1)


class ProviderAccountResponse(BaseModel):
    id: UUID | str
    merchant_id: UUID | str
    provider_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value) if value else None
