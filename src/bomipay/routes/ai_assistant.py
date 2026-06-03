import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.ai_assistant import AIAssistantService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["AI Assistant"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance, Role.support)


class AIQueryRequest(BaseModel):
    merchant_id: Optional[str] = None
    query: str
    transaction_id: Optional[str] = None
    settlement_id: Optional[str] = None


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/ai-assistant/health")
async def ai_health():
    categories = AIAssistantService.get_categories()
    return {"status": "ok", "categories_supported": len(categories), "version": "1.0"}


@router.get("/ai-assistant/categories")
async def ai_categories():
    return {"categories": AIAssistantService.get_categories()}


@router.post("/ai-assistant/query")
async def ai_query(
    payload: AIQueryRequest,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = str(payload.merchant_id or current_user.merchant_id or "")
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)

    result = await AIAssistantService.query(
        db,
        merchant_id=merchant_id,
        query=payload.query,
        transaction_id=payload.transaction_id,
        settlement_id=payload.settlement_id,
    )
    return result
