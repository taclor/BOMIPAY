import logging
from ..worker import app, CallbackTask

logger = logging.getLogger("bomipay")


@app.task(bind=True, task_cls=CallbackTask)
def export_transactions_csv(self, merchant_id: str, date_from: str, date_to: str) -> dict:
    """Generate and export transactions CSV file."""
    try:
        logger.info(
            "export_transactions_csv.started",
            extra={
                "merchant_id": merchant_id,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "date_from": date_from,
            "date_to": date_to,
            "download_url": None,
            "row_count": 0,
        }
    except Exception as exc:
        logger.error(
            "export_transactions_csv.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise


@app.task(bind=True, task_cls=CallbackTask)
def export_settlements_csv(self, merchant_id: str, date_from: str, date_to: str) -> dict:
    """Generate and export settlements CSV file."""
    try:
        logger.info(
            "export_settlements_csv.started",
            extra={
                "merchant_id": merchant_id,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "date_from": date_from,
            "date_to": date_to,
            "download_url": None,
            "row_count": 0,
        }
    except Exception as exc:
        logger.error(
            "export_settlements_csv.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise
