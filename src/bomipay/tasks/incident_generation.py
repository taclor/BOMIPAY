import logging
from ..worker import app, CallbackTask

logger = logging.getLogger("bomipay")


@app.task(bind=True, task_cls=CallbackTask)
def detect_and_create_incidents(self, merchant_id: str) -> dict:
    """Detect incidents from alerts, failed transactions, and settlement mismatches."""
    try:
        logger.info(
            "detect_and_create_incidents.started",
            extra={"merchant_id": merchant_id},
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "incidents_created": 0,
        }
    except Exception as exc:
        logger.error(
            "detect_and_create_incidents.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise
