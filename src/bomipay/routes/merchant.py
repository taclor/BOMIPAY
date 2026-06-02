from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.auth import UserResponse
from ..schemas.merchant import (
    MerchantCreateRequest,
    MerchantMemberCreateRequest,
    MerchantResponse,
    ProviderAccountCreateRequest,
    ProviderAccountResponse,
    UpdateMerchantRequest,
)
from ..services.auth import get_current_active_user, require_role
from ..services.audit import log_audit_event
from ..services.merchant import MerchantService, ProviderAccountService
from ..services.user import UserService

router = APIRouter()


@router.get("/merchant/me", response_model=MerchantResponse)
async def get_merchant_profile(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantResponse:
    merchant = await MerchantService.get_merchant(db, current_user.merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    return merchant


@router.patch("/merchant/me", response_model=MerchantResponse)
async def update_merchant_profile(
    payload: UpdateMerchantRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantResponse:
    merchant = await MerchantService.get_merchant(db, current_user.merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    merchant = await MerchantService.update_merchant(db, merchant, **payload.model_dump(exclude_none=True))
    log_audit_event(
        db,
        event_type="merchant.update",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"merchant_id": str(merchant.id), "updates": payload.model_dump(exclude_none=True)},
    )
    await db.commit()
    return merchant


@router.post(
    "/merchant/provider-accounts",
    response_model=ProviderAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_account(
    payload: ProviderAccountCreateRequest,
    current_user=Depends(require_role(Role.merchant_user, Role.admin)),
    db: AsyncSession = Depends(get_db),
) -> ProviderAccountResponse:
    if not current_user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant context required")
    account = await ProviderAccountService.create_provider_account(
        db,
        merchant_id=current_user.merchant_id,
        provider_name=payload.provider_name,
        api_key=payload.api_key,
        secret=payload.secret,
    )
    log_audit_event(
        db,
        event_type="provider_account.create",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"provider_account_id": str(account.id), "merchant_id": str(account.merchant_id)},
    )
    await db.commit()
    return account


@router.get("/merchant/provider-accounts", response_model=list[ProviderAccountResponse])
async def list_provider_accounts(
    current_user=Depends(require_role(Role.merchant_user, Role.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderAccountResponse]:
    if not current_user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant context required")
    accounts = await ProviderAccountService.list_provider_accounts(db, current_user.merchant_id)
    return accounts


@router.post("/merchants", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    payload: MerchantCreateRequest,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
) -> MerchantResponse:
    merchant = await MerchantService.create_merchant(
        db,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        business_type=payload.business_type,
        country=payload.country,
    )
    log_audit_event(
        db,
        event_type="merchant.create",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"merchant_id": str(merchant.id), "name": merchant.name},
    )
    await db.commit()
    return merchant


@router.get("/merchants/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantResponse:
    merchant = await MerchantService.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    if current_user.role != Role.admin and current_user.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return merchant


@router.patch("/merchants/{merchant_id}", response_model=MerchantResponse)
async def patch_merchant(
    merchant_id: str,
    payload: UpdateMerchantRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantResponse:
    merchant = await MerchantService.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    if current_user.role != Role.admin and current_user.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    merchant = await MerchantService.update_merchant(db, merchant, **payload.model_dump(exclude_none=True))
    log_audit_event(
        db,
        event_type="merchant.update",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"merchant_id": str(merchant.id), "updates": payload.model_dump(exclude_none=True)},
    )
    await db.commit()
    return merchant


@router.get("/merchants/{merchant_id}/members", response_model=list[UserResponse])
async def list_merchant_members(
    merchant_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    merchant = await MerchantService.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    if current_user.role != Role.admin and current_user.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    members = await MerchantService.list_members(db, merchant_id)
    return members


@router.post("/merchants/{merchant_id}/members", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant_member(
    merchant_id: str,
    payload: MerchantMemberCreateRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    merchant = await MerchantService.get_merchant(db, merchant_id)
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    if current_user.role != Role.admin and current_user.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    existing = await UserService.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await UserService.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        merchant_id=merchant.id,
    )
    log_audit_event(
        db,
        event_type="merchant.member.create",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"merchant_id": str(merchant.id), "user_id": str(user.id), "role": user.role.value},
    )
    await db.commit()
    return user
