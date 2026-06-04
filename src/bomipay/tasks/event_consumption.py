import asyncio
import logging

from ..worker import app
from ..services.event_processor import EventProcessor
from ..observability.streams import EventStreamManager

logger = logging.getLogger("bomipay")


@app.task(bind=True, name="bomipay.tasks.event_consumption.consume_and_process_events")
def consume_and_process_events(self):
    """
    Periodic task that consumes and processes events from Redis Streams.

    This task:
    1. Connects to Redis Stream
    2. Reads pending events for consumer group
    3. Processes each event
    4. ACKs event (marks processed)

    Should be scheduled to run frequently (e.g., every 10 seconds).
    """
    try:
        logger.info("Starting event consumption task")

        asyncio.run(EventProcessor.consume_events(block_once=True))

        logger.info("Event consumption task completed")
    except Exception as e:
        logger.error(f"Error in event consumption task: {str(e)}", exc_info=True)
        raise


@app.task(bind=True, name="bomipay.tasks.event_consumption.setup_event_streams")
def setup_event_streams_task(self):
    """
    One-time setup task to initialize Redis Streams and consumer groups.
    """
    try:
        logger.info("Setting up event streams")

        result = asyncio.run(EventStreamManager.setup_event_streams())

        logger.info(f"Event streams setup completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error setting up event streams: {str(e)}", exc_info=True)
        raise


@app.task(bind=True, name="bomipay.tasks.event_consumption.get_stream_info")
def get_stream_info_task(self):
    """
    Get current stream and consumer group info.
    """
    try:
        result = asyncio.run(EventStreamManager.get_stream_info())
        logger.info(f"Stream info: {result}")
        return result
    except Exception as e:
        logger.error(f"Error getting stream info: {str(e)}", exc_info=True)
        raise


@app.task(bind=True, name="bomipay.tasks.event_consumption.get_pending_messages")
def get_pending_messages_task(self):
    """
    Get pending (unacked) messages in consumer group.
    """
    try:
        result = asyncio.run(EventStreamManager.get_pending_messages())
        logger.info(f"Pending messages: {result}")
        return result
    except Exception as e:
        logger.error(f"Error getting pending messages: {str(e)}", exc_info=True)
        raise
