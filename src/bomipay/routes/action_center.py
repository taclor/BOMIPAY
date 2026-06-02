import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.action_center import ActionCenterService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Action Center"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/action-center")
async def get_actions(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return {"actions": await ActionCenterService.get_actions(db, effective)}
