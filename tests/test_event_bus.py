import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bomipay.config import settings
from src.bomipay.models.event import DomainEvent, EventType
from src.bomipay.services.event_publisher import EventPublisher
from src.bomipay.services.event_processor import EventProcessor
from src.bomipay.services.event_handlers import EventHandlers
from src.bomipay.services.event_replay import EventReplayer
from src.bomipay.observability.streams import EventStreamManager


@pytest.fixture
def redis_client():
    """Get Redis client for testing."""
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


@pytest.fixture
async def cleanup_streams(redis_client):
    """Cleanup streams before and after tests."""
    yield
    # Cleanup
    if redis_client:
        try:
            redis_client.delete(EventPublisher.STREAM_NAME)
            redis_client.xgroup_destroy(EventPublisher.STREAM_NAME, EventProcessor.CONSUMER_GROUP)
        except Exception:
            pass
        redis_client.close()


class TestEventPublisher:
    """Tests for EventPublisher service."""

    @pytest.mark.asyncio
    async def test_publish_event_stores_in_database(self, db_session: AsyncSession):
        """Test that published event is stored in domain_events table."""
        merchant_id = uuid.uuid4()
        aggregate_id = str(uuid.uuid4())
        payload = {"amount": 1000, "currency": "USD"}

        # Mock Redis to avoid connection errors
        with patch('src.bomipay.services.event_publisher.Redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis.from_url.return_value = mock_redis_instance
            mock_redis_instance.xadd.return_value = "1-0"

            event = await EventPublisher.publish_event(
                db_session,
                EventType.transaction_created,
                str(merchant_id),
                aggregate_id,
                "transaction",
                payload,
            )

        assert event.id is not None
        assert event.event_type == EventType.transaction_created.value
        assert str(event.merchant_id) == str(merchant_id)
        assert event.aggregate_id == aggregate_id
        assert event.aggregate_type == "transaction"
        assert event.correlation_id is not None

        # Verify in database
        result = await db_session.execute(
            select(DomainEvent).where(DomainEvent.id == event.id)
        )
        stored_event = result.scalars().first()
        assert stored_event is not None
        assert stored_event.event_type == EventType.transaction_created.value

    @pytest.mark.asyncio
    async def test_publish_event_to_redis_stream(
        self, db_session: AsyncSession, redis_client, cleanup_streams
    ):
        """Test that published event appears in Redis Stream."""
        merchant_id = uuid.uuid4()
        aggregate_id = str(uuid.uuid4())
        payload = {"amount": 1000}

        if not redis_client:
            pytest.skip("Redis not available")

        await EventPublisher.publish_event(
            db_session,
            EventType.settlement_received,
            str(merchant_id),
            aggregate_id,
            "settlement",
            payload,
        )

        # Check stream length
        stream_length = redis_client.xlen(EventPublisher.STREAM_NAME)
        assert stream_length > 0

        # Read from stream
        messages = redis_client.xread({EventPublisher.STREAM_NAME: "0"}, count=1)
        assert messages is not None
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_publish_event_with_correlation_id(self, db_session: AsyncSession):
        """Test that correlation_id propagates correctly."""
        merchant_id = uuid.uuid4()
        correlation_id = str(uuid.uuid4())
        aggregate_id = str(uuid.uuid4())

        event = await EventPublisher.publish_event(
            db_session,
            EventType.incident_created,
            str(merchant_id),
            aggregate_id,
            "incident",
            {},
            correlation_id=correlation_id,
        )

        assert event.correlation_id == correlation_id

        # Verify in database
        result = await db_session.execute(
            select(DomainEvent).where(DomainEvent.correlation_id == correlation_id)
        )
        stored_event = result.scalars().first()
        assert stored_event is not None

    @pytest.mark.asyncio
    async def test_publish_multiple_events_in_order(self, db_session: AsyncSession):
        """Test that multiple events are published in order."""
        merchant_id = uuid.uuid4()
        aggregate_id = str(uuid.uuid4())

        event_ids = []
        for i in range(3):
            event = await EventPublisher.publish_event(
                db_session,
                EventType.transaction_created,
                str(merchant_id),
                aggregate_id,
                "transaction",
                {"index": i},
            )
            event_ids.append(event.id)
            await db_session.flush()

        # Verify order in database
        result = await db_session.execute(
            select(DomainEvent)
            .where(DomainEvent.merchant_id == merchant_id)
            .order_by(DomainEvent.created_at)
        )
        events = result.scalars().all()
        assert len(events) == 3
        assert [e.id for e in events] == event_ids

    @pytest.mark.asyncio
    async def test_check_event_exists_idempotency(self, db_session: AsyncSession):
        """Test idempotency checking with correlation_id."""
        merchant_id = uuid.uuid4()
        correlation_id = str(uuid.uuid4())

        # Event doesn't exist yet
        exists = await EventPublisher.check_event_exists(db_session, correlation_id)
        assert not exists

        # Publish event with correlation_id
        await EventPublisher.publish_event(
            db_session,
            EventType.transaction_created,
            str(merchant_id),
            str(uuid.uuid4()),
            "transaction",
            {},
            correlation_id=correlation_id,
        )

        # Event should exist now
        exists = await EventPublisher.check_event_exists(db_session, correlation_id)
        assert exists


class TestEventProcessor:
    """Tests for EventProcessor service."""

    @pytest.mark.asyncio
    async def test_consumer_group_creation(self, redis_client, cleanup_streams):
        """Test that consumer group is created on first consume."""
        if not redis_client:
            pytest.skip("Redis not available")

        # Setup stream first
        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})

        # Attempt to consume (should create group)
        await EventProcessor.reset_consumer_group(
            EventPublisher.STREAM_NAME, EventProcessor.CONSUMER_GROUP, "0"
        )

        # Verify consumer group exists
        groups = redis_client.xinfo_groups(EventPublisher.STREAM_NAME)
        group_names = [g["name"] for g in groups]
        assert EventProcessor.CONSUMER_GROUP in group_names

    @pytest.mark.asyncio
    async def test_get_pending_messages(self, redis_client, cleanup_streams):
        """Test getting pending messages from consumer group."""
        if not redis_client:
            pytest.skip("Redis not available")

        # Setup stream and consumer group
        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})
        try:
            redis_client.xgroup_create(
                EventPublisher.STREAM_NAME,
                EventProcessor.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except redis_client.ResponseError:
            pass

        pending_info = await EventProcessor.get_pending_messages(
            EventPublisher.STREAM_NAME, EventProcessor.CONSUMER_GROUP
        )

        assert pending_info is not None
        assert "stream" in pending_info


class TestEventHandlers:
    """Tests for EventHandlers service."""

    @pytest.mark.asyncio
    async def test_handler_dispatch(self):
        """Test that correct handler is called for event type."""
        payload = {
            "event_id": str(uuid.uuid4()),
            "merchant_id": str(uuid.uuid4()),
            "aggregate_id": str(uuid.uuid4()),
            "amount": 1000,
        }

        # Should not raise
        await EventHandlers.handle_event(EventType.transaction_created.value, payload)

    @pytest.mark.asyncio
    async def test_handler_for_all_event_types(self):
        """Test that handlers exist for all event types."""
        for event_type in EventType:
            assert event_type.value in EventHandlers.HANDLERS
            handler = EventHandlers.HANDLERS[event_type.value]
            assert callable(handler)


class TestEventReplayer:
    """Tests for EventReplayer service."""

    @pytest.mark.asyncio
    async def test_replay_events_for_merchant(self, db_session: AsyncSession):
        """Test replaying events for a merchant."""
        merchant_id = uuid.uuid4()

        # Publish some events
        for i in range(3):
            await EventPublisher.publish_event(
                db_session,
                EventType.transaction_created,
                str(merchant_id),
                str(uuid.uuid4()),
                "transaction",
                {"index": i},
            )
            await db_session.flush()

        # Replay events
        count = await EventReplayer.replay_events_for_merchant(db_session, str(merchant_id))
        assert count == 3

    @pytest.mark.asyncio
    async def test_replay_events_for_aggregate(self, db_session: AsyncSession):
        """Test replaying events for a specific aggregate."""
        merchant_id = uuid.uuid4()
        aggregate_id = str(uuid.uuid4())

        # Publish multiple events for same aggregate
        for i in range(2):
            await EventPublisher.publish_event(
                db_session,
                EventType.transaction_created,
                str(merchant_id),
                aggregate_id,
                "transaction",
                {"index": i},
            )
            await db_session.flush()

        # Replay events for aggregate
        count = await EventReplayer.replay_events_for_aggregate(
            db_session, "transaction", aggregate_id
        )
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_events_for_merchant(self, db_session: AsyncSession):
        """Test getting events for a merchant."""
        merchant_id = uuid.uuid4()

        # Publish some events
        for i in range(3):
            await EventPublisher.publish_event(
                db_session,
                EventType.transaction_created,
                str(merchant_id),
                str(uuid.uuid4()),
                "transaction",
                {"index": i},
            )
            await db_session.flush()

        # Get events
        events = await EventReplayer.get_events_for_merchant(db_session, str(merchant_id))
        assert len(events) == 3
        assert all(e["merchant_id"] == str(merchant_id) for e in events)


class TestEventStreamManager:
    """Tests for EventStreamManager service."""

    @pytest.mark.asyncio
    async def test_setup_event_streams(self, redis_client, cleanup_streams):
        """Test setting up event streams and consumer groups."""
        if not redis_client:
            pytest.skip("Redis not available")

        result = await EventStreamManager.setup_event_streams()

        assert "stream_created" in result
        assert "consumer_group_created" in result

    @pytest.mark.asyncio
    async def test_get_stream_info(self, redis_client, cleanup_streams):
        """Test getting stream information."""
        if not redis_client:
            pytest.skip("Redis not available")

        # Setup stream
        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})

        info = await EventStreamManager.get_stream_info(EventPublisher.STREAM_NAME)
        assert info is not None
        assert info["stream"] == EventPublisher.STREAM_NAME
        assert info["length"] >= 1

    @pytest.mark.asyncio
    async def test_get_stream_length(self, redis_client, cleanup_streams):
        """Test getting stream length."""
        if not redis_client:
            pytest.skip("Redis not available")

        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})
        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data2"})

        length = await EventStreamManager.get_stream_length(EventPublisher.STREAM_NAME)
        assert length == 2

    @pytest.mark.asyncio
    async def test_reset_consumer_group(self, redis_client, cleanup_streams):
        """Test resetting consumer group."""
        if not redis_client:
            pytest.skip("Redis not available")

        # Setup
        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})
        try:
            redis_client.xgroup_create(
                EventPublisher.STREAM_NAME,
                EventProcessor.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except redis_client.ResponseError:
            pass

        # Reset
        await EventStreamManager.reset_consumer_group(
            EventPublisher.STREAM_NAME, EventProcessor.CONSUMER_GROUP, "$"
        )

        # Verify reset
        info = await EventStreamManager.get_stream_info(EventPublisher.STREAM_NAME)
        groups = info["consumer_groups"]
        assert len(groups) > 0

    @pytest.mark.asyncio
    async def test_purge_stream(self, redis_client, cleanup_streams):
        """Test purging stream."""
        if not redis_client:
            pytest.skip("Redis not available")

        redis_client.xadd(EventPublisher.STREAM_NAME, {"test": "data"})

        length_before = redis_client.xlen(EventPublisher.STREAM_NAME)
        assert length_before > 0

        await EventStreamManager.purge_stream(EventPublisher.STREAM_NAME)

        # Stream should be deleted or empty
        try:
            length_after = redis_client.xlen(EventPublisher.STREAM_NAME)
            assert length_after == 0
        except redis_client.ResponseError:
            # Stream doesn't exist anymore
            pass


class TestEventBusIntegration:
    """Integration tests for event bus."""

    @pytest.mark.asyncio
    async def test_end_to_end_event_flow(
        self, db_session: AsyncSession, redis_client, cleanup_streams
    ):
        """Test complete event flow: publish -> stream -> consume -> handle."""
        if not redis_client:
            pytest.skip("Redis not available")

        merchant_id = uuid.uuid4()
        aggregate_id = str(uuid.uuid4())
        payload = {"amount": 1000, "currency": "USD"}

        # 1. Publish event
        event = await EventPublisher.publish_event(
            db_session,
            EventType.transaction_created,
            str(merchant_id),
            aggregate_id,
            "transaction",
            payload,
        )

        # 2. Verify in database
        result = await db_session.execute(
            select(DomainEvent).where(DomainEvent.id == event.id)
        )
        stored_event = result.scalars().first()
        assert stored_event is not None

        # 3. Verify in Redis Stream
        stream_length = redis_client.xlen(EventPublisher.STREAM_NAME)
        assert stream_length > 0

        # 4. Read from stream
        messages = redis_client.xread({EventPublisher.STREAM_NAME: "0"}, count=1)
        assert messages is not None
        stream_name, message_list = messages[0]
        message_id, message_data = message_list[0]
        assert message_data["event_type"] == EventType.transaction_created.value

    @pytest.mark.asyncio
    async def test_event_correlation_id_propagation(self, db_session: AsyncSession):
        """Test that correlation_id propagates through event chain."""
        merchant_id = uuid.uuid4()
        correlation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        event = await EventPublisher.publish_event(
            db_session,
            EventType.transaction_created,
            str(merchant_id),
            str(uuid.uuid4()),
            "transaction",
            {},
            correlation_id=correlation_id,
            request_id=request_id,
        )

        assert event.correlation_id == correlation_id
        assert event.request_id == request_id

        # Verify in database
        result = await db_session.execute(
            select(DomainEvent).where(DomainEvent.id == event.id)
        )
        stored_event = result.scalars().first()
        assert stored_event.correlation_id == correlation_id
        assert stored_event.request_id == request_id
