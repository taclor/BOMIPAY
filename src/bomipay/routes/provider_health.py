from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.provider_health import ProviderHealthMetrics
from ..services.auth import get_current_active_user
from ..services.provider_health import ProviderHealthService

router = APIRouter()


class HealthMetricResponse(BaseModel):
    provider_name: str
    metric_date: date
    reliability_score_bps: int
    settlement_lag_score_bps: int
    webhook_failure_score_bps: int
    health_status: str
    transaction_count: int
    transaction_success_count: int
    settlement_count: int
    webhook_event_count: int
    outage_windows: int

    class Config:
        from_attributes = True


class ProviderHealthResponse(BaseModel):
    provider_name: str
    reliability_score_bps: int
    settlement_lag_score_bps: int
    webhook_failure_score_bps: int
    health_status: str
    transaction_success_rate: float
    settlement_count: int
    webhook_event_count: int

    class Config:
        from_attributes = True


@router.get("/providers/health-metrics", response_model=list[HealthMetricResponse])
async def get_provider_health_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get health metrics for all providers for a merchant within date range."""

    query = select(ProviderHealthMetrics).where(
        ProviderHealthMetrics.merchant_id == current_user.merchant_id
    )

    if date_from:
        query = query.where(ProviderHealthMetrics.metric_date >= date_from)
    if date_to:
        query = query.where(ProviderHealthMetrics.metric_date <= date_to)

    query = query.order_by(ProviderHealthMetrics.metric_date.desc())

    result = await db.execute(query)
    metrics = result.scalars().all()

    return [HealthMetricResponse.from_orm(m) for m in metrics]


@router.get("/providers/{provider_name}/health-metrics", response_model=ProviderHealthResponse)
async def get_provider_health_detail(
    provider_name: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current health status for a specific provider."""

    # Get latest metric for this provider
    result = await db.execute(
        select(ProviderHealthMetrics)
        .where(
            and_(
                ProviderHealthMetrics.merchant_id == current_user.merchant_id,
                ProviderHealthMetrics.provider_name == provider_name,
            )
        )
        .order_by(ProviderHealthMetrics.metric_date.desc())
        .limit(1)
    )

    metric = result.scalars().first()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No health data found")

    # Calculate success rate
    success_rate = (
        (metric.transaction_success_count / metric.transaction_count * 100)
        if metric.transaction_count > 0
        else 0.0
    )

    return ProviderHealthResponse(
        provider_name=metric.provider_name,
        reliability_score_bps=metric.reliability_score_bps,
        settlement_lag_score_bps=metric.settlement_lag_score_bps,
        webhook_failure_score_bps=metric.webhook_failure_score_bps,
        health_status=metric.health_status,
        transaction_success_rate=success_rate,
        settlement_count=metric.settlement_count,
        webhook_event_count=metric.webhook_event_count,
    )


@router.get("/providers/{provider_name}/health-history", response_model=list[HealthMetricResponse])
async def get_provider_health_history(
    provider_name: str,
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get daily health metrics for a provider over the last N days."""

    result = await db.execute(
        select(ProviderHealthMetrics)
        .where(
            and_(
                ProviderHealthMetrics.merchant_id == current_user.merchant_id,
                ProviderHealthMetrics.provider_name == provider_name,
            )
        )
        .order_by(ProviderHealthMetrics.metric_date.asc())
        .limit(days)
    )

    metrics = result.scalars().all()
    return [HealthMetricResponse.from_orm(m) for m in metrics]


@router.post("/providers/{provider_name}/calculate-health")
async def calculate_provider_health(
    provider_name: str,
    calc_date: Optional[date] = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger health calculation for a provider on a specific date."""

    target_date = calc_date or date.today()

    metric = await ProviderHealthService.calculate_daily_metrics(
        db, current_user.merchant_id, provider_name, target_date
    )
    await db.commit()

    return HealthMetricResponse.from_orm(metric)
