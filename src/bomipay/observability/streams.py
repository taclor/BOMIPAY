import logging
from typing import Optional

from redis import Redis

from ..config import settings

logger = logging.getLogger("bomipay")


class EventStreamManager:
    """Manages Redis Streams initialization and monitoring."""

    STREAM_NAME = "bomipay.events"
    CONSUMER_GROUP = "bomi-pay-processors"
    RETENTION_MS = 86400000  # 24 hours

    @staticmethod
    async def setup_event_streams() -> dict:
        """
        Initialize Redis Streams and consumer groups.

        Returns:
            Setup result information
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        result = {"stream_created": False, "consumer_group_created": False}

        try:
            # Check if stream exists by trying to get info
            try:
                info = redis.xinfo_stream(EventStreamManager.STREAM_NAME)
                logger.info(f"Stream {EventStreamManager.STREAM_NAME} already exists")
            except redis.ResponseError as e:
                if "no such key" in str(e).lower():
                    # Create stream with initial message
                    redis.xadd(
                        EventStreamManager.STREAM_NAME,
                        {"initialized": "true"},
                    )
                    redis.xdel(EventStreamManager.STREAM_NAME, redis.xrange(EventStreamManager.STREAM_NAME, count=1)[0][0])
                    logger.info(f"Created stream: {EventStreamManager.STREAM_NAME}")
                    result["stream_created"] = True
                else:
                    raise

            # Try to create consumer group
            try:
                redis.xgroup_create(
                    EventStreamManager.STREAM_NAME,
                    EventStreamManager.CONSUMER_GROUP,
                    id="0",
                    mkstream=True,
                )
                logger.info(f"Created consumer group: {EventStreamManager.CONSUMER_GROUP}")
                result["consumer_group_created"] = True
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"Consumer group {EventStreamManager.CONSUMER_GROUP} already exists")
                else:
                    raise

            # Set retention policy
            try:
                redis.xtrim(EventStreamManager.STREAM_NAME, maxlen=0, approximate=False)
            except redis.ResponseError:
                pass

            logger.info("Event streams setup complete")
            return result

        finally:
            redis.close()

    @staticmethod
    async def get_stream_info(stream_name: str = STREAM_NAME) -> Optional[dict]:
        """
        Get stream information (length, consumer groups, etc.).

        Args:
            stream_name: Name of Redis Stream

        Returns:
            Stream info or None if stream doesn't exist
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            info = redis.xinfo_stream(stream_name)
            consumer_groups = redis.xinfo_groups(stream_name)

            return {
                "stream": stream_name,
                "length": info.get("length", 0),
                "first_entry_id": info.get("first-entry", [None])[0],
                "last_entry_id": info.get("last-entry", [None])[0],
                "consumer_groups": [
                    {
                        "name": group.get("name"),
                        "consumers": group.get("consumers", 0),
                        "pending": group.get("pending", 0),
                    }
                    for group in consumer_groups
                ],
            }
        except redis.ResponseError as e:
            if "no such key" in str(e).lower():
                return None
            raise
        finally:
            redis.close()

    @staticmethod
    async def get_stream_length(stream_name: str = STREAM_NAME) -> int:
        """Get number of entries in stream."""
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return redis.xlen(stream_name)
        finally:
            redis.close()

    @staticmethod
    async def purge_stream(stream_name: str = STREAM_NAME):
        """Delete all entries from stream."""
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            redis.delete(stream_name)
            logger.info(f"Purged stream: {stream_name}")
        finally:
            redis.close()

    @staticmethod
    async def reset_consumer_group(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
        start_id: str = "0",
    ):
        """
        Reset consumer group to replay events from beginning.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name
            start_id: ID to start from ("0" = beginning, "$" = end)
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            redis.xgroup_setid(stream_name, consumer_group, start_id)
            logger.info(f"Reset consumer group {consumer_group} to {start_id}")
        finally:
            redis.close()

    @staticmethod
    async def get_pending_messages(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
    ) -> dict:
        """
        Get pending (unacked) messages in consumer group.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name

        Returns:
            Pending messages info
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            pending = redis.xpending(stream_name, consumer_group)
            return {
                "stream": stream_name,
                "consumer_group": consumer_group,
                "pending_count": pending.get("pending", 0) if isinstance(pending, dict) else 0,
                "pending": pending,
            }
        finally:
            redis.close()

    @staticmethod
    async def delete_consumer_group(
        stream_name: str = STREAM_NAME,
        consumer_group: str = CONSUMER_GROUP,
    ):
        """
        Delete consumer group.

        Args:
            stream_name: Name of Redis Stream
            consumer_group: Consumer group name
        """
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            redis.xgroup_destroy(stream_name, consumer_group)
            logger.info(f"Deleted consumer group {consumer_group} from {stream_name}")
        finally:
            redis.close()
