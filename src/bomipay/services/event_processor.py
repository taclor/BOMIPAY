import asyncio
import json
import logging
from typing import Optional

from redis import Redis

from ..config import settings
from .event_handlers import EventHandlers

logger = logging.getLogger("bomipay")


class EventProcessor:
    """Consumes and processes events from Redis Streams."""

    STREAM_NAME = "bomipay.events"
    CONSUMER_GROUP = "bomi-pay-processors"
    CONSUMER_NAME = "processor-1"
    BLOCK_MS = 1000

    @staticmethod
    async def consume_events(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
        last_id: str = "0",
        consumer_name: str = CONSUMER_NAME,
        block_once: bool = False,
    ):
        """
        Listen on Redis Stream and process events.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name
            last_id: Starting ID ("0" = from beginning, "$" = from now)
            consumer_name: Name of this consumer
            block_once: If True, process one batch and return
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        try:
            # Try to create consumer group (fails silently if exists)
            try:
                redis.xgroup_create(stream_name, consumer_group, id=last_id, mkstream=True)
                logger.info(f"Created consumer group: {consumer_group}")
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

            logger.info(f"Started consuming from {stream_name}")

            while True:
                try:
                    # Read pending messages for this consumer
                    messages = redis.xreadgroup(
                        {stream_name: ">"},
                        consumer_group,
                        consumer_name,
                        count=10,
                        block=EventProcessor.BLOCK_MS,
                    )

                    if not messages:
                        if block_once:
                            break
                        continue

                    for stream, message_list in messages:
                        for message_id, message_data in message_list:
                            try:
                                await EventProcessor._process_event(
                                    message_data, redis, stream_name, consumer_group, message_id
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error processing message: {message_id}",
                                    extra={"message_id": message_id, "error": str(e)},
                                    exc_info=True,
                                )

                    if block_once:
                        break

                except asyncio.CancelledError:
                    logger.info("Event consumption stopped")
                    break
                except Exception as e:
                    logger.error(f"Error reading from stream: {str(e)}", exc_info=True)
                    if block_once:
                        break
                    await asyncio.sleep(5)

        finally:
            redis.close()

    @staticmethod
    async def _process_event(
        message_data: dict,
        redis: Redis,
        stream_name: str,
        consumer_group: str,
        message_id: str,
    ):
        """
        Process individual event.

        Args:
            message_data: Event data from Redis
            redis: Redis client
            stream_name: Name of stream
            consumer_group: Consumer group name
            message_id: Message ID for ACK
        """
        try:
            event_type = message_data.get("event_type", "")
            payload_json = message_data.get("payload", "{}")

            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}

            payload.update(
                {
                    "event_id": message_data.get("event_id"),
                    "merchant_id": message_data.get("merchant_id"),
                    "aggregate_id": message_data.get("aggregate_id"),
                    "correlation_id": message_data.get("correlation_id"),
                }
            )

            logger.info(f"Processing event: {event_type}", extra={"event_type": event_type})

            await EventHandlers.handle_event(event_type, payload)

            # ACK message after successful processing
            redis.xack(stream_name, consumer_group, message_id)
            logger.info(f"ACKed message: {message_id}")

        except Exception as e:
            logger.error(f"Failed to process event: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def get_consumer_group_info(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
    ) -> dict:
        """
        Get information about consumer group.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name

        Returns:
            Consumer group info
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            info = redis.xinfo_groups(stream_name)
            for group in info:
                if group.get("name") == consumer_group:
                    return group
            return {}
        finally:
            redis.close()

    @staticmethod
    async def get_pending_messages(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
    ) -> list:
        """
        Get pending (unacked) messages in consumer group.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name

        Returns:
            List of pending messages
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            pending = redis.xpending(stream_name, consumer_group)
            return {"stream": stream_name, **pending}
        finally:
            redis.close()

    @staticmethod
    async def reset_consumer_group(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
        start_id: str = "0",
    ):
        """
        Reset consumer group to replay from beginning (for recovery).
        Creates the group if it does not already exist.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name
            start_id: ID to start from ("0" = beginning, "$" = end)
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            try:
                redis.xgroup_create(stream_name, consumer_group, id=start_id, mkstream=True)
                logger.info(f"Created consumer group {consumer_group} at {start_id}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    # Group exists — just reposition it
                    redis.xgroup_setid(stream_name, consumer_group, start_id)
                    logger.info(f"Reset consumer group {consumer_group} to {start_id}")
                else:
                    raise
        finally:
            redis.close()

    @staticmethod
    async def delete_consumer_group(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
    ):
        """
        Delete consumer group (for cleanup).

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            redis.xgroup_destroy(stream_name, consumer_group)
            logger.info(f"Deleted consumer group {consumer_group}")
        finally:
            redis.close()
