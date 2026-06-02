from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.notification import Notification
from ..schemas.notification import NotificationListQuery, NotificationResponse
from ..services.auth import get_current_active_user
from ..services.notification import NotificationService
from ..models.user import Role

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    if user_id and current_user.role != Role.admin and user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    effective_user_id = user_id if current_user.role == Role.admin else str(current_user.id)
    merchant_id = current_user.merchant_id if current_user.role != Role.admin else None

    notifications = await NotificationService.list_notifications(
        db,
        merchant_id=merchant_id,
        user_id=effective_user_id,
        status=status,
    )
    return notifications


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    notification = await NotificationService.get_notification(db, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if current_user.role != Role.admin and notification.merchant_id != current_user.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if notification.user_id and notification.user_id != current_user.id and current_user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    notification = await NotificationService.mark_as_read(db, notification)
    await db.commit()
    return notification
