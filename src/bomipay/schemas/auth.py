from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr


class UserRegisterRequest(BaseModel):
    full_name: constr(min_length=2, max_length=255)
    email: EmailStr
    phone: constr(min_length=10, max_length=24)
    password: constr(min_length=12)
    merchant_name: Optional[constr(min_length=2, max_length=255)] = None
    business_type: Optional[constr(max_length=128)] = None
    country: Optional[constr(max_length=64)] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field("bearer")


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
