import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.notification import Notification, NotificationChannel, NotificationStatus

logger = logging.getLogger("bomipay.notification")


class NotificationService:
    MAX_RETRY_COUNT = 5
    BASE_RETRY_BACKOFF_SECONDS = 30

    @staticmethod
    def _current_time() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        merchant_id,
        channel: str,
        message: str,
        user_id=None,
        alert_id=None,
        delivery_key: str | None = None,
        metadata_json: dict | None = None,
        provider_response: dict | None = None,
    ) -> Notification:
        if delivery_key:
            existing = await NotificationService.get_by_delivery_key(db, merchant_id, delivery_key)
            if existing:
                return existing

        if channel == NotificationChannel.in_app.value:
            status = NotificationStatus.unread.value
        else:
            status = NotificationStatus.pending.value

        notification = Notification(
            merchant_id=merchant_id,
            user_id=user_id,
            alert_id=alert_id,
            channel=channel,
            message=message,
            delivery_key=delivery_key,
            status=status,
            metadata_json=metadata_json,
            provider_response=provider_response,
        )
        db.add(notification)
        await db.flush()
        await db.refresh(notification)
        return notification

    @staticmethod
    async def get_by_delivery_key(db: AsyncSession, merchant_id, delivery_key: str) -> Notification | None:
        result = await db.execute(
            select(Notification)
            .where(Notification.merchant_id == merchant_id)
            .where(Notification.delivery_key == delivery_key)
        )
        return result.scalars().first()

    @staticmethod
    async def list_notifications(db: AsyncSession, merchant_id=None, user_id=None, status=None):
        query = select(Notification)
        if merchant_id is not None:
            query = query.where(Notification.merchant_id == merchant_id)
        if user_id is not None:
            query = query.where((Notification.user_id == user_id) | (Notification.user_id.is_(None)))
        if status is not None:
            query = query.where(Notification.status == status)
        result = await db.execute(query.order_by(Notification.created_at.desc()))
        return result.scalars().all()

    @staticmethod
    async def get_notification(db: AsyncSession, notification_id):
        result = await db.execute(select(Notification).where(Notification.id == notification_id))
        return result.scalars().first()

    @staticmethod
    async def mark_as_read(db: AsyncSession, notification: Notification) -> Notification:
        notification.status = NotificationStatus.read.value
        await db.flush()
        await db.refresh(notification)
        return notification

    @staticmethod
    def email_adapter(recipient_email: str, subject: str, body: str) -> dict:
        logger.info(
            "notification.email.adapter.invoke",
            extra={
                "recipient_email": recipient_email,
                "subject": subject,
                "body_length": len(body),
            },
        )
        return {"provider": "console", "delivered": True}

    @staticmethod
    async def attempt_delivery(db: AsyncSession, notification_id: str, recipient_email: str) -> Notification | None:
        now = NotificationService._current_time()
        result = await db.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.status.in_([NotificationStatus.pending.value, NotificationStatus.retry_scheduled.value, NotificationStatus.failed.value]))
            .where(or_(Notification.next_retry_at.is_(None), Notification.next_retry_at <= now))
            .values(status=NotificationStatus.sending.value, last_attempt_at=now)
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount == 0:
            return None

        notification = await NotificationService.get_notification(db, notification_id)
        if not notification:
            return None

        try:
            response = NotificationService.email_adapter(recipient_email, notification.channel, notification.message)
            notification.provider_response = response
            notification.channel_message_id = response.get("message_id") if isinstance(response, dict) else None
            notification.status = NotificationStatus.sent.value
            notification.sent_at = now
            notification.delivery_error = None
            notification.next_retry_at = None
            await db.flush()
            await db.refresh(notification)
            logger.info(
                "notification.delivery.success",
                extra={"notification_id": str(notification.id), "recipient_email": recipient_email},
            )
            return notification
        except Exception as exc:
            await NotificationService._schedule_retry(db, notification, str(exc), now)
            logger.warning(
                "notification.delivery.failure",
                extra={
                    "notification_id": str(notification.id),
                    "error": str(exc),
                    "retry_count": notification.retry_count,
                },
            )
            return notification

    @staticmethod
    async def _schedule_retry(db: AsyncSession, notification: Notification, error_message: str, now: datetime):
        notification.delivery_error = error_message
        notification.retry_count += 1
        notification.last_attempt_at = now
        if notification.retry_count >= NotificationService.MAX_RETRY_COUNT:
            notification.status = NotificationStatus.abandoned.value
            notification.next_retry_at = None
            logger.error(
                "notification.delivery.abandoned",
                extra={"notification_id": str(notification.id), "retry_count": notification.retry_count},
            )
        else:
            delay = NotificationService.BASE_RETRY_BACKOFF_SECONDS * (2 ** (notification.retry_count - 1))
            notification.status = NotificationStatus.retry_scheduled.value
            notification.next_retry_at = now + timedelta(seconds=delay)
            logger.info(
                "notification.delivery.retry_scheduled",
                extra={
                    "notification_id": str(notification.id),
                    "retry_count": notification.retry_count,
                    "next_retry_at": notification.next_retry_at.isoformat(),
                },
            )
        await db.flush()
        await db.refresh(notification)
