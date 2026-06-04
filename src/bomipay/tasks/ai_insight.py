import logging
from ..worker import app, CallbackTask

logger = logging.getLogger("bomipay")


@app.task(bind=True, task_cls=CallbackTask)
def generate_ai_insight(self, merchant_id: str, insight_type: str) -> dict:
    """Generate AI insights (money-at-risk, incident analysis, etc.)."""
    try:
        logger.info(
            "generate_ai_insight.started",
            extra={"merchant_id": merchant_id, "insight_type": insight_type},
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "insight_type": insight_type,
            "insight": None,
        }
    except Exception as exc:
        logger.error(
            "generate_ai_insight.failed",
            extra={"merchant_id": merchant_id, "insight_type": insight_type, "error": str(exc)},
            exc_info=True,
        )
        raise


@app.task
def cache_ai_responses(merchant_id: str) -> dict:
    """Pre-compute and cache top 5 common AI queries for a merchant."""
    try:
        logger.info(
            "cache_ai_responses.started",
            extra={"merchant_id": merchant_id},
        )
        return {
            "status": "ok",
            "merchant_id": merchant_id,
            "cached_queries": 0,
        }
    except Exception as exc:
        logger.error(
            "cache_ai_responses.failed",
            extra={"merchant_id": merchant_id, "error": str(exc)},
            exc_info=True,
        )
        raise
