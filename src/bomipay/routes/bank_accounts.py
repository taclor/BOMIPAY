import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.bank_account import (
    BankAccountCreate,
    BankAccountListResponse,
    BankAccountResponse,
    BankAccountUpdate,
    BankAccountVerifyResponse,
)
from ..services.audit import log_audit_event
from ..services.auth import get_current_active_user, require_role
from ..services.bank_account import BankAccountService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Bank Accounts"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post("/bank-accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    payload: BankAccountCreate,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = str(payload.merchant_id or current_user.merchant_id)
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)

    account = await BankAccountService.create(
        db,
        merchant_id=merchant_id,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
        account_name=payload.account_name,
        currency=payload.currency,
        purpose=payload.purpose,
        bank_code=payload.bank_code,
        metadata_json=payload.metadata_json,
    )
    log_audit_event(
        db,
        event_type="bank_account.created",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"bank_account_id": str(account.id), "merchant_id": merchant_id},
    )
    await db.commit()
    return BankAccountResponse(**BankAccountService.to_response_dict(account))


@router.get("/bank-accounts", response_model=BankAccountListResponse)
async def list_bank_accounts(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)

    accounts = await BankAccountService.list_for_merchant(db, effective_merchant_id)
    items = [BankAccountResponse(**BankAccountService.to_response_dict(a)) for a in accounts]
    return BankAccountListResponse(items=items, total=len(items))


@router.get("/bank-accounts/{bank_account_id}", response_model=BankAccountResponse)
async def get_bank_account(
    bank_account_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    account = await BankAccountService.get_by_id(db, bank_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    _check_merchant_access(current_user, str(account.merchant_id))
    return BankAccountResponse(**BankAccountService.to_response_dict(account))


@router.patch("/bank-accounts/{bank_account_id}", response_model=BankAccountResponse)
async def update_bank_account(
    bank_account_id: str,
    payload: BankAccountUpdate,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    account = await BankAccountService.get_by_id(db, bank_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    _check_merchant_access(current_user, str(account.merchant_id))

    updates = payload.model_dump(exclude_none=True)
    account = await BankAccountService.update(db, account, updates)
    log_audit_event(
        db,
        event_type="bank_account.updated",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"bank_account_id": bank_account_id, "updates": updates},
    )
    await db.commit()
    return BankAccountResponse(**BankAccountService.to_response_dict(account))


@router.delete("/bank-accounts/{bank_account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_account(
    bank_account_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    account = await BankAccountService.get_by_id(db, bank_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    _check_merchant_access(current_user, str(account.merchant_id))

    await BankAccountService.soft_delete(db, account)
    log_audit_event(
        db,
        event_type="bank_account.deleted",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"bank_account_id": bank_account_id},
    )
    await db.commit()


@router.post("/bank-accounts/{bank_account_id}/verify", response_model=BankAccountVerifyResponse)
async def verify_bank_account(
    bank_account_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    account = await BankAccountService.get_by_id(db, bank_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    _check_merchant_access(current_user, str(account.merchant_id))

    await BankAccountService.initiate_verification(db, account)
    await BankAccountService.verify_with_adapter(db, account)
    log_audit_event(
        db,
        event_type="bank_account.verified",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"bank_account_id": bank_account_id},
    )
    await db.commit()
    return BankAccountVerifyResponse(
        bank_account_id=bank_account_id,
        verification_status=account.verification_status,
        message="Bank account verification completed",
    )
