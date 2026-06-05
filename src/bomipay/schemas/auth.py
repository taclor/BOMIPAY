from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr, field_serializer, field_validator


class UserRegisterRequest(BaseModel):
    full_name: constr(min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[constr(min_length=10, max_length=24)] = None
    password: constr(min_length=12)
    merchant_name: Optional[constr(min_length=2, max_length=255)] = None
    business_type: Optional[constr(max_length=128)] = None
    country: Optional[constr(max_length=64)] = None

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserInToken(BaseModel):
    id: UUID | str
    email: EmailStr
    full_name: str
    role: str
    merchant_id: Optional[UUID | str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str | None, _info) -> str | None:
        return str(value) if value else None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field("bearer")
    user: Optional[UserInToken] = None
    merchant_id: Optional[str] = None  # convenience field for backward compat


class UserResponse(BaseModel):
    id: UUID | str
    email: EmailStr
    full_name: str
    phone: str
    role: str
    merchant_id: Optional[UUID | str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str | None, _info) -> str | None:
        return str(value) if value else None
