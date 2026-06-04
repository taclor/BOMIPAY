import logging
from ..worker import app

logger = logging.getLogger("bomipay")


@app.task
def aggregate_alerts(merchant_id: str) -> dict:
    """Aggregate similar alerts, suppress duplicates, and escalate severity."""
    try:
        logger.info(
            "aggregate_alerts.started",
            extra={"merchant_id": merchant_id},
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "alerts_aggregated": 0,
            "alerts_suppressed": 0,
        }
    except Exception as exc:
        logger.error(
            "aggregate_alerts.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise


@app.task
def send_alert_notification(alert_id: str) -> dict:
    """Send alert notification via webhook/email/SMS."""
    try:
        logger.info(
            "send_alert_notification.started",
            extra={"alert_id": alert_id},
        )
        return {
            "status": "ok",
            "alert_id": alert_id,
            "sent": False,
        }
    except Exception as exc:
        logger.error(
            "send_alert_notification.failed",
            extra={"alert_id": alert_id, "error": str(exc)},
            exc_info=True,
        )
        raise
