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


def _resolve_merchant(merchant_id: Optional[str], current_user) -> str:
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return effective


@router.get("/action-center")
async def get_actions(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = _resolve_merchant(merchant_id, current_user)
    return {"actions": await ActionCenterService.get_actions(db, effective)}


@router.get("/action-center/stats")
async def get_action_stats(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = _resolve_merchant(merchant_id, current_user)
    return await ActionCenterService.get_action_stats(db, effective)


@router.post("/action-center/{action_type}/dismiss")
async def dismiss_action(
    action_type: str,
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = _resolve_merchant(merchant_id, current_user)
    return await ActionCenterService.dismiss_action(db, effective, action_type)
