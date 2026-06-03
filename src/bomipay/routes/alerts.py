from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.alert import Alert, AlertStatus
from ..schemas.alert import AlertActionRequest, AlertResponse
from ..services.alert import AlertService
from ..services.auth import get_current_active_user

router = APIRouter()


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    alert_type: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[AlertResponse]:
    filters = {"status": status, "severity": severity, "alert_type": alert_type}
    alerts = await AlertService.list_alerts(db, current_user.merchant_id, filters)
    return alerts


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .where(Alert.merchant_id == current_user.merchant_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    payload: AlertActionRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .where(Alert.merchant_id == current_user.merchant_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert = await AlertService.update_alert_status(db, alert, payload.status)
    await db.commit()
    return alert


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .where(Alert.merchant_id == current_user.merchant_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = AlertStatus.acknowledged.value
    alert.acknowledged_at = datetime.utcnow()
    await db.flush()
    await db.refresh(alert)
    await db.commit()
    return alert


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .where(Alert.merchant_id == current_user.merchant_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = AlertStatus.resolved.value
    alert.resolved_at = datetime.utcnow()
    await db.flush()
    await db.refresh(alert)
    await db.commit()
    return alert
