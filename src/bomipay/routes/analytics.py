import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.money_at_risk import MoneyAtRiskService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Analytics"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/analytics/money-at-risk")
async def money_at_risk(
    merchant_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return await MoneyAtRiskService.calculate(db, effective, date_from=date_from, date_to=date_to)
