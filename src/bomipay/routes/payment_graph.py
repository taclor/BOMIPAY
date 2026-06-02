import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.payment_graph import PaymentGraphService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Payment Graph"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance, Role.support)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/payment-graph/transactions/{transaction_id}")
async def transaction_graph(
    transaction_id: str,
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    graph = await PaymentGraphService.get_transaction_graph(db, effective, transaction_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return graph


@router.get("/payment-graph/incidents/{incident_id}")
async def incident_graph(
    incident_id: str,
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    graph = await PaymentGraphService.get_incident_graph(db, effective, incident_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return graph


@router.get("/payment-graph/merchants/{merchant_id_path}/overview")
async def merchant_graph_overview(
    merchant_id_path: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    _check_merchant_access(current_user, merchant_id_path)
    return await PaymentGraphService.get_merchant_overview(db, merchant_id_path)
