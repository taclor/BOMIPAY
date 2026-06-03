import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.money_at_risk import MoneyAtRiskService
from ..schemas.money_at_risk import (
    MoneyAtRiskResponse,
    MoneyAtRiskTrendResponse,
    MoneyAtRiskTrendPoint,
    MoneyAtRiskBreakdownResponse,
    MoneyAtRiskBreakdown,
    MoneyAtRiskAtRiskTransactionsResponse,
    AtRiskTransaction,
    MoneyAtRiskProjectionResponse,
    ProjectionPoint,
    MoneyAtRiskAlertResponse,
    MoneyAtRiskAlertItem,
)

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
    """Get current MAR snapshot (legacy endpoint)."""
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return await MoneyAtRiskService.calculate(db, effective, date_from=date_from, date_to=date_to)


@router.get("/money-at-risk/current")
async def get_current_mar(
    merchant_id: Optional[str] = Query(None),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskResponse:
    """Get current MAR snapshot for a merchant.
    
    Calculates pending transactions, unreconciled funds, failed transfers,
    and generates risk score and breakdowns.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    mar_data = await MoneyAtRiskService.calculate_mar_for_merchant(db, effective)
    return MoneyAtRiskResponse(**mar_data)


@router.get("/money-at-risk/trend")
async def get_mar_trend(
    merchant_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskTrendResponse:
    """Get historical MAR trend over the last N days.
    
    Returns time-series data showing MAR evolution, enabling trend analysis
    and pattern recognition for improving financial controls.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    trend_data = await MoneyAtRiskService.get_mar_trend(db, effective, days=days)
    return MoneyAtRiskTrendResponse(
        merchant_id=effective,
        days=days,
        trend=[MoneyAtRiskTrendPoint(**point) for point in trend_data],
    )


@router.get("/money-at-risk/breakdown")
async def get_mar_breakdown(
    merchant_id: Optional[str] = Query(None),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskBreakdownResponse:
    """Get detailed breakdown of MAR by provider and status.
    
    Shows which providers and transaction statuses contribute most to
    financial exposure, enabling targeted risk mitigation.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    mar_data = await MoneyAtRiskService.calculate_mar_for_merchant(db, effective)
    
    # Convert breakdown data
    by_provider = {
        k: MoneyAtRiskBreakdown(**v)
        for k, v in mar_data["breakdown_by_provider"].items()
    }
    by_status = {
        k: MoneyAtRiskBreakdown(**v)
        for k, v in mar_data["breakdown_by_status"].items()
    }
    
    return MoneyAtRiskBreakdownResponse(
        merchant_id=effective,
        period_date=mar_data["period_date"],
        total_at_risk=mar_data["total_at_risk"],
        by_provider=by_provider,
        by_status=by_status,
    )


@router.get("/money-at-risk/at-risk-transactions")
async def get_at_risk_transactions(
    merchant_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="Filter by category: pending, unreconciled, or failed"),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskAtRiskTransactionsResponse:
    """List transactions contributing to MAR.
    
    Returns detailed information about each transaction in the Money-at-Risk
    calculation, enabling drill-down investigation.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    if category and category not in ("pending", "unreconciled", "failed"):
        raise HTTPException(status_code=400, detail="category must be pending, unreconciled, or failed")
    
    txns_data = await MoneyAtRiskService.identify_at_risk_transactions(
        db, effective, category=category, limit=limit
    )
    
    return MoneyAtRiskAtRiskTransactionsResponse(
        merchant_id=effective,
        category=category,
        count=len(txns_data),
        transactions=[AtRiskTransaction(**t) for t in txns_data],
    )


@router.get("/money-at-risk/projection")
async def get_mar_projection(
    merchant_id: Optional[str] = Query(None),
    days_ahead: int = Query(30, ge=1, le=90),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskProjectionResponse:
    """Estimate when MAR will resolve based on trends.
    
    Projects future MAR values based on historical reduction rates,
    providing estimated resolution timelines and confidence levels.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    projection_data = await MoneyAtRiskService.project_resolution(
        db, effective, days_ahead=days_ahead
    )
    
    return MoneyAtRiskProjectionResponse(
        merchant_id=effective,
        estimated_resolution_date=projection_data["estimated_resolution_date"],
        days_to_resolution=projection_data["days_to_resolution"],
        daily_reduction_rate=projection_data["daily_reduction_rate"],
        confidence=projection_data["confidence"],
        reason=projection_data.get("reason"),
        projection=[ProjectionPoint(**p) for p in projection_data["projection"]],
    )


@router.get("/money-at-risk/alerts")
async def get_mar_alerts(
    merchant_id: Optional[str] = Query(None),
    threshold: int = Query(1000000, ge=0, description="Amount threshold in minor units"),
    score_threshold: int = Query(70, ge=0, le=100),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> MoneyAtRiskAlertResponse:
    """Get alerts for high MAR or worsening trends.
    
    Returns a list of alerts when MAR exceeds thresholds or trends are worsening,
    with recommendations for remedial action.
    """
    effective = merchant_id or str(current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    
    alerts_data = await MoneyAtRiskService.get_alerts_for_high_mar(
        db, effective, mar_threshold=float(threshold), score_threshold=score_threshold
    )
    
    alerts = [MoneyAtRiskAlertItem(**alert) for alert in alerts_data]
    high_risk = any(a.severity == "high" for a in alerts)
    
    return MoneyAtRiskAlertResponse(
        merchant_id=effective,
        alerts=alerts,
        has_alerts=len(alerts) > 0,
        high_risk=high_risk,
    )

