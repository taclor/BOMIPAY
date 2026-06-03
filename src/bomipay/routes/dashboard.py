import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.dashboard import DashboardService
from ..schemas.dashboard import (
    DashboardResponse,
    DashboardMetricsResponse,
    ProviderHealthResponse,
    OperationalStatusResponse,
    ActivitiesResponse,
    PerformanceMetricsResponse,
    AnomalyIndicator,
)

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Dashboard"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/dashboard")
async def get_dashboard(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Get complete mission control dashboard view."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    dashboard_data = await DashboardService.get_realtime_dashboard(db, effective_merchant_id)
    return DashboardResponse(merchant_id=effective_merchant_id, **dashboard_data)


@router.get("/dashboard/metrics")
async def get_metrics(
    period: str = Query("today", description="today, week, month, or year"),
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """Get metrics for different time periods."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    if period not in ["today", "week", "month", "year"]:
        raise HTTPException(status_code=400, detail="period must be today, week, month, or year")
    
    metrics = await DashboardService.get_metrics_summary(db, effective_merchant_id, period)
    
    # Get all periods for comprehensive response
    today = await DashboardService.get_metrics_summary(db, effective_merchant_id, "today")
    week = await DashboardService.get_metrics_summary(db, effective_merchant_id, "week")
    month = await DashboardService.get_metrics_summary(db, effective_merchant_id, "month")
    year = await DashboardService.get_metrics_summary(db, effective_merchant_id, "year")
    
    return DashboardMetricsResponse(today=today, week=week, month=month, year=year)


@router.get("/dashboard/providers")
async def get_provider_health(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderHealthResponse]:
    """Get provider health status for all providers."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    return await DashboardService._get_provider_health(db, effective_merchant_id)


@router.get("/dashboard/status")
async def get_operational_status(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> OperationalStatusResponse:
    """Get overall operational status."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    metrics = await DashboardService._aggregate_core_metrics(db, effective_merchant_id)
    performance = await DashboardService._calculate_performance_metrics(db, effective_merchant_id)
    status = await DashboardService._get_operational_status(db, effective_merchant_id, metrics, performance)
    
    from datetime import datetime, timezone
    return OperationalStatusResponse(
        overall_status=status["status"],
        system_health_score=status["health_score"],
        key_issues=status["key_issues"],
        last_updated=datetime.now(timezone.utc),
    )


@router.get("/dashboard/activities")
async def get_recent_activities(
    limit: int = Query(20, ge=1, le=100),
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[ActivitiesResponse]:
    """Get recent activities feed."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    activities = await DashboardService._get_recent_activities(db, effective_merchant_id, limit)
    return [ActivitiesResponse(**activity) for activity in activities]


@router.get("/dashboard/performance")
async def get_performance_metrics(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> PerformanceMetricsResponse:
    """Get KPI performance metrics."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    performance = await DashboardService._calculate_performance_metrics(db, effective_merchant_id)
    return PerformanceMetricsResponse(**performance)


@router.get("/dashboard/anomalies")
async def get_anomalies(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[AnomalyIndicator]:
    """Get detected anomalies."""
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)
    
    metrics = await DashboardService._aggregate_core_metrics(db, effective_merchant_id)
    performance = await DashboardService._calculate_performance_metrics(db, effective_merchant_id)
    anomalies = await DashboardService._detect_anomalies(db, effective_merchant_id, metrics, performance)
    
    return [AnomalyIndicator(**anomaly) for anomaly in anomalies]


@router.get("/dashboard/mission-control")
async def mission_control(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Legacy mission control endpoint (maintained for backward compatibility)."""
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    return await DashboardService.get_mission_control(db, effective)
