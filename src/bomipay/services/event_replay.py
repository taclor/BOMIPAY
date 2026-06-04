import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.event import DomainEvent, EventType
from .event_handlers import EventHandlers

logger = logging.getLogger("bomipay")


class EventReplayer:
    """Replay events for debugging and recovery."""

    @staticmethod
    async def replay_events_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        event_types: Optional[list[str]] = None,
    ) -> int:
        """
        Replay all events for a merchant from domain_events table.

        Args:
            db: Database session
            merchant_id: Merchant ID
            event_types: Optional list of specific event types to replay

        Returns:
            Number of events replayed
        """
        query = select(DomainEvent).where(DomainEvent.merchant_id == merchant_id)

        if event_types:
            query = query.where(DomainEvent.event_type.in_(event_types))

        query = query.order_by(DomainEvent.created_at)

        result = await db.execute(query)
        events = result.scalars().all()

        count = 0
        for event in events:
            try:
                payload = json.loads(event.payload_json)
                payload.update(
                    {
                        "event_id": str(event.id),
                        "merchant_id": str(event.merchant_id),
                        "aggregate_id": event.aggregate_id,
                        "aggregate_type": event.aggregate_type,
                        "correlation_id": event.correlation_id,
                    }
                )

                await EventHandlers.handle_event(event.event_type, payload)
                count += 1
                logger.info(
                    f"Replayed event {count}: {event.event_type}",
                    extra={"event_id": str(event.id)},
                )
            except Exception as e:
                logger.error(
                    f"Error replaying event {event.id}: {str(e)}",
                    extra={"event_id": str(event.id)},
                    exc_info=True,
                )
                raise

        logger.info(f"Replayed {count} events for merchant {merchant_id}")
        return count

    @staticmethod
    async def replay_events_since_timestamp(
        db: AsyncSession,
        since: datetime,
        event_types: Optional[list[str]] = None,
    ) -> int:
        """
        Replay all events since a specific timestamp.

        Args:
            db: Database session
            since: Replay events created after this timestamp
            event_types: Optional list of specific event types to replay

        Returns:
            Number of events replayed
        """
        query = select(DomainEvent).where(DomainEvent.created_at >= since)

        if event_types:
            query = query.where(DomainEvent.event_type.in_(event_types))

        query = query.order_by(DomainEvent.created_at)

        result = await db.execute(query)
        events = result.scalars().all()

        count = 0
        for event in events:
            try:
                payload = json.loads(event.payload_json)
                payload.update(
                    {
                        "event_id": str(event.id),
                        "merchant_id": str(event.merchant_id),
                        "aggregate_id": event.aggregate_id,
                        "aggregate_type": event.aggregate_type,
                        "correlation_id": event.correlation_id,
                    }
                )

                await EventHandlers.handle_event(event.event_type, payload)
                count += 1
                logger.info(
                    f"Replayed event {count}: {event.event_type}",
                    extra={"event_id": str(event.id)},
                )
            except Exception as e:
                logger.error(
                    f"Error replaying event {event.id}: {str(e)}",
                    extra={"event_id": str(event.id)},
                    exc_info=True,
                )
                raise

        logger.info(f"Replayed {count} events since {since}")
        return count

    @staticmethod
    async def replay_events_for_aggregate(
        db: AsyncSession,
        aggregate_type: str,
        aggregate_id: str,
    ) -> int:
        """
        Replay all events for a specific aggregate (e.g., transaction, incident).

        Args:
            db: Database session
            aggregate_type: Type of aggregate (e.g., "transaction", "incident")
            aggregate_id: ID of aggregate

        Returns:
            Number of events replayed
        """
        query = (
            select(DomainEvent)
            .where(
                and_(
                    DomainEvent.aggregate_type == aggregate_type,
                    DomainEvent.aggregate_id == aggregate_id,
                )
            )
            .order_by(DomainEvent.created_at)
        )

        result = await db.execute(query)
        events = result.scalars().all()

        count = 0
        for event in events:
            try:
                payload = json.loads(event.payload_json)
                payload.update(
                    {
                        "event_id": str(event.id),
                        "merchant_id": str(event.merchant_id),
                        "aggregate_id": event.aggregate_id,
                        "aggregate_type": event.aggregate_type,
                        "correlation_id": event.correlation_id,
                    }
                )

                await EventHandlers.handle_event(event.event_type, payload)
                count += 1
                logger.info(
                    f"Replayed event {count}: {event.event_type}",
                    extra={"event_id": str(event.id)},
                )
            except Exception as e:
                logger.error(
                    f"Error replaying event {event.id}: {str(e)}",
                    extra={"event_id": str(event.id)},
                    exc_info=True,
                )
                raise

        logger.info(
            f"Replayed {count} events for aggregate {aggregate_type}:{aggregate_id}"
        )
        return count

    @staticmethod
    async def get_events_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        limit: int = 100,
        event_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Get events for a merchant (for debugging).

        Args:
            db: Database session
            merchant_id: Merchant ID
            limit: Maximum number of events to return
            event_types: Optional list of specific event types

        Returns:
            List of event dicts
        """
        query = (
            select(DomainEvent)
            .where(DomainEvent.merchant_id == merchant_id)
            .order_by(DomainEvent.created_at.desc())
            .limit(limit)
        )

        if event_types:
            query = query.where(DomainEvent.event_type.in_(event_types))

        result = await db.execute(query)
        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "merchant_id": str(event.merchant_id),
                "aggregate_id": event.aggregate_id,
                "aggregate_type": event.aggregate_type,
                "correlation_id": event.correlation_id,
                "created_at": event.created_at.isoformat(),
                "published_at": event.published_at.isoformat() if event.published_at else None,
            }
            for event in events
        ]

    @staticmethod
    async def get_events_for_aggregate(
        db: AsyncSession,
        aggregate_type: str,
        aggregate_id: str,
    ) -> list[dict]:
        """
        Get all events for a specific aggregate.

        Args:
            db: Database session
            aggregate_type: Type of aggregate
            aggregate_id: ID of aggregate

        Returns:
            List of event dicts
        """
        query = (
            select(DomainEvent)
            .where(
                and_(
                    DomainEvent.aggregate_type == aggregate_type,
                    DomainEvent.aggregate_id == aggregate_id,
                )
            )
            .order_by(DomainEvent.created_at)
        )

        result = await db.execute(query)
        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "merchant_id": str(event.merchant_id),
                "aggregate_id": event.aggregate_id,
                "aggregate_type": event.aggregate_type,
                "correlation_id": event.correlation_id,
                "created_at": event.created_at.isoformat(),
                "published_at": event.published_at.isoformat() if event.published_at else None,
            }
            for event in events
        ]
