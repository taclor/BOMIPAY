import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..db import get_db
from ..schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from ..services.auth import authenticate_user, decode_token, get_current_active_user
from ..services.audit import log_audit_event
from ..services.security import create_access_token, create_refresh_token
from ..services.user import UserService
from ..models.user import Role

router = APIRouter()


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    existing = await UserService.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        merchant = await UserService.create_merchant_for_user(
            db,
            merchant_name=payload.merchant_name or payload.full_name,
            email=payload.email,
            phone=payload.phone,
            business_type=payload.business_type,
            country=payload.country,
        )
        user = await UserService.create_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            phone=payload.phone,
            role=Role.merchant_user,
            merchant_id=merchant.id,
        )
        log_audit_event(
            db,
            event_type="user.register",
            actor_id=str(user.id),
            actor_role=user.role.value,
            event_payload={"email": user.email, "merchant_id": str(merchant.id)},
        )
        await db.commit()
        return user
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user with provided data",
        )


@router.post("/auth/login", response_model=TokenResponse)
async def login_user(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    log_audit_event(
        db,
        event_type="user.login",
        actor_id=str(user.id),
        actor_role=user.role.value,
        event_payload={"email": user.email},
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    payload_data = decode_token(payload.refresh_token)
    if payload_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user_id = payload_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    user = await UserService.get_by_id(db, user_uuid)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    log_audit_event(
        db,
        event_type="user.token_refresh",
        actor_id=str(user.id),
        actor_role=user.role.value,
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    current_user=Depends(get_current_active_user),
) -> UserResponse:
    return current_user
