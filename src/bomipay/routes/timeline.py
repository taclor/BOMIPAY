import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.timeline import TimelineService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Timeline"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/timeline/payments")
async def payment_timeline(
    merchant_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    event_types: Optional[str] = Query(default=None, description="Comma-separated event types to include"),
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    parsed_event_types = (
        {t.strip() for t in event_types.split(",") if t.strip()}
        if event_types
        else None
    )
    return await TimelineService.get_payment_timeline(
        db,
        merchant_id=effective,
        date_from=date_from,
        date_to=date_to,
        status=status,
        provider=provider,
        event_types=parsed_event_types,
        skip=skip,
        limit=limit,
    )


@router.get("/timeline/transactions/{transaction_id}/events")
async def transaction_lifecycle(
    transaction_id: str,
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    result = await TimelineService.get_transaction_lifecycle(
        db,
        merchant_id=effective,
        transaction_id=transaction_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.get("/timeline/summary")
async def timeline_summary(
    merchant_id: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return await TimelineService.get_timeline_summary(db, merchant_id=effective, days=days)
