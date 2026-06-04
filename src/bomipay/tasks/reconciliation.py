import logging
from ..worker import app, CallbackTask

logger = logging.getLogger("bomipay")


@app.task(bind=True, task_cls=CallbackTask)
def run_reconciliation(self, merchant_id: str, date_from: str, date_to: str) -> dict:
    """Trigger reconciliation service for a merchant within a date range."""
    try:
        logger.info(
            "run_reconciliation.started",
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
            "reconciliation_run_id": None,
        }
    except Exception as exc:
        logger.error(
            "run_reconciliation.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise


@app.task(bind=True, task_cls=CallbackTask)
def generate_reconciliation_report(self, reconciliation_run_id: str) -> dict:
    """Generate and export reconciliation report."""
    try:
        logger.info(
            "generate_reconciliation_report.started",
            extra={"reconciliation_run_id": reconciliation_run_id},
        )
        return {
            "status": "ok",
            "reconciliation_run_id": reconciliation_run_id,
            "report_url": None,
        }
    except Exception as exc:
        logger.error(
            "generate_reconciliation_report.failed",
            extra={"reconciliation_run_id": reconciliation_run_id, "error": str(exc)},
            exc_info=True,
        )
        raise
