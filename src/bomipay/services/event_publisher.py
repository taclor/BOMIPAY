import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.event import DomainEvent, EventType

logger = logging.getLogger("bomipay")


class EventPublisher:
    """Publishes domain events to database and Redis Streams for processing."""

    STREAM_NAME = "bomipay.events"
    STREAM_RETENTION_MS = 86400000  # 24 hours

    @staticmethod
    async def publish_event(
        db: AsyncSession,
        event_type: EventType,
        merchant_id: str,
        aggregate_id: str,
        aggregate_type: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> DomainEvent:
        """
        Publish a domain event to both database and Redis Streams.

        1. Store event in domain_events table (append-only)
        2. Try to publish to Redis Streams for async processing
        3. Return persisted event (even if Redis publish fails)

        Args:
            db: Database session
            event_type: Type of event
            merchant_id: ID of merchant
            aggregate_id: ID of aggregate (e.g., transaction_id, incident_id)
            aggregate_type: Type of aggregate (e.g., "transaction", "incident")
            payload: Event payload as dict
            correlation_id: Optional correlation ID for tracing
            request_id: Optional request ID for tracing

        Returns:
            Persisted DomainEvent
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        payload_json = json.dumps(payload)

        event = DomainEvent(
            id=uuid.uuid4(),
            event_type=event_type.value,
            merchant_id=merchant_id,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            correlation_id=correlation_id,
            request_id=request_id,
            payload_json=payload_json,
        )

        db.add(event)
        await db.flush()

        try:
            stream_id = await EventPublisher._publish_to_stream(event)
            logger.info(
                "Event published",
                extra={
                    "event_id": str(event.id),
                    "event_type": event_type.value,
                    "merchant_id": str(merchant_id),
                    "stream_id": stream_id,
                    "correlation_id": correlation_id,
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to publish event to Redis Stream (will retry via processor)",
                extra={
                    "event_id": str(event.id),
                    "event_type": event_type.value,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )
            # Don't fail the entire operation - event is persisted in DB

        return event

    @staticmethod
    async def _publish_to_stream(event: DomainEvent) -> str:
        """
        Publish event to Redis Stream.

        Args:
            event: Domain event to publish

        Returns:
            Stream entry ID from Redis
        """
        from ..config import settings

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            stream_data = {
                "event_id": str(event.id),
                "event_type": event.event_type,
                "merchant_id": str(event.merchant_id),
                "aggregate_id": event.aggregate_id,
                "aggregate_type": event.aggregate_type,
                "correlation_id": event.correlation_id or "",
                "request_id": event.request_id or "",
                "payload": event.payload_json,
                "published_at": event.published_at.isoformat() if event.published_at else "",
            }
            stream_id = redis.xadd(
                EventPublisher.STREAM_NAME,
                stream_data,
                approximate=True,
            )
            
            redis.expire(EventPublisher.STREAM_NAME, EventPublisher.STREAM_RETENTION_MS // 1000)
            return stream_id
        finally:
            redis.close()

    @staticmethod
    async def check_event_exists(db: AsyncSession, correlation_id: str) -> bool:
        """
        Check if an event with given correlation_id already exists (idempotency).

        Args:
            db: Database session
            correlation_id: Correlation ID to check

        Returns:
            True if event exists, False otherwise
        """
        from sqlalchemy import select

        result = await db.execute(
            select(DomainEvent).where(DomainEvent.correlation_id == correlation_id).limit(1)
        )
        return result.scalars().first() is not None
