import logging
from ..worker import app, CallbackTask

logger = logging.getLogger("bomipay")


@app.task
def post_process_webhook(webhook_event_id: str) -> dict:
    """Post-process webhook event: enrich transaction model, create incidents/alerts if needed."""
    try:
        logger.info(
            "post_process_webhook.started",
            extra={"webhook_event_id": webhook_event_id},
        )
        return {
            "status": "ok",
            "webhook_event_id": webhook_event_id,
            "enriched": False,
        }
    except Exception as exc:
        logger.error(
            "post_process_webhook.failed",
            extra={"webhook_event_id": webhook_event_id, "error": str(exc)},
            exc_info=True,
        )
        raise


@app.task
def aggregate_webhook_events(merchant_id: str) -> dict:
    """Aggregate webhook events into alerts/incidents for a merchant."""
    try:
        logger.info(
            "aggregate_webhook_events.started",
            extra={"merchant_id": merchant_id},
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "events_aggregated": 0,
        }
    except Exception as exc:
        logger.error(
            "aggregate_webhook_events.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise
