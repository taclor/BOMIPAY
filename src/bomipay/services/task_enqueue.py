"""Service for enqueuing Celery tasks."""
import logging
from typing import Optional

logger = logging.getLogger("bomipay")


class TaskEnqueueService:
    """Helper service for enqueuing async tasks."""

    @staticmethod
    def enqueue_provider_sync(
        merchant_id: str,
        provider_account_id: str,
        sync_type: str = "transactions",
        countdown: int = 5,
    ) -> Optional[str]:
        """Enqueue a provider sync task."""
        try:
            from ..tasks.provider_sync import (
                sync_provider_transactions,
                sync_provider_settlements,
                sync_provider_transfers,
                sync_provider_refunds,
            )

            task_map = {
                "transactions": sync_provider_transactions,
                "settlements": sync_provider_settlements,
                "transfers": sync_provider_transfers,
                "refunds": sync_provider_refunds,
            }

            task = task_map.get(sync_type, sync_provider_transactions)
            result = task.apply_async(
                args=(merchant_id, provider_account_id),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_provider_sync",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                    "sync_type": sync_type,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_provider_sync.failed",
                extra={"merchant_id": merchant_id, "error": str(exc)},
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_webhook_post_process(webhook_event_id: str, countdown: int = 1) -> Optional[str]:
        """Enqueue webhook post-processing task."""
        try:
            from ..tasks.webhook_processing import post_process_webhook

            result = post_process_webhook.apply_async(
                args=(webhook_event_id,),
                countdown=countdown,
            )
            logger.info(
                "enqueue_webhook_post_process",
                extra={
                    "task_id": result.id,
                    "webhook_event_id": webhook_event_id,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_webhook_post_process.failed",
                extra={"webhook_event_id": webhook_event_id, "error": str(exc)},
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_reconciliation(
        merchant_id: str,
        date_from: str,
        date_to: str,
        countdown: int = 5,
    ) -> Optional[str]:
        """Enqueue reconciliation task."""
        try:
            from ..tasks.reconciliation import run_reconciliation

            result = run_reconciliation.apply_async(
                args=(merchant_id, date_from, date_to),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_reconciliation",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_reconciliation.failed",
                extra={"merchant_id": merchant_id, "error": str(exc)},
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_incident_detection(merchant_id: str, countdown: int = 0) -> Optional[str]:
        """Enqueue incident detection task."""
        try:
            from ..tasks.incident_generation import detect_and_create_incidents

            result = detect_and_create_incidents.apply_async(
                args=(merchant_id,),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_incident_detection",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_incident_detection.failed",
                extra={"merchant_id": merchant_id, "error": str(exc)},
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_ai_insight(
        merchant_id: str,
        insight_type: str,
        countdown: int = 0,
    ) -> Optional[str]:
        """Enqueue AI insight generation task."""
        try:
            from ..tasks.ai_insight import generate_ai_insight

            result = generate_ai_insight.apply_async(
                args=(merchant_id, insight_type),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_ai_insight",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                    "insight_type": insight_type,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_ai_insight.failed",
                extra={
                    "merchant_id": merchant_id,
                    "insight_type": insight_type,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_export_transactions(
        merchant_id: str,
        date_from: str,
        date_to: str,
        countdown: int = 5,
    ) -> Optional[str]:
        """Enqueue transaction export task."""
        try:
            from ..tasks.exports import export_transactions_csv

            result = export_transactions_csv.apply_async(
                args=(merchant_id, date_from, date_to),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_export_transactions",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_export_transactions.failed",
                extra={"merchant_id": merchant_id, "error": str(exc)},
                exc_info=True,
            )
            return None

    @staticmethod
    def enqueue_export_settlements(
        merchant_id: str,
        date_from: str,
        date_to: str,
        countdown: int = 5,
    ) -> Optional[str]:
        """Enqueue settlement export task."""
        try:
            from ..tasks.exports import export_settlements_csv

            result = export_settlements_csv.apply_async(
                args=(merchant_id, date_from, date_to),
                countdown=countdown,
                retry=True,
            )
            logger.info(
                "enqueue_export_settlements",
                extra={
                    "task_id": result.id,
                    "merchant_id": merchant_id,
                },
            )
            return result.id
        except Exception as exc:
            logger.error(
                "enqueue_export_settlements.failed",
                extra={"merchant_id": merchant_id, "error": str(exc)},
                exc_info=True,
            )
            return None
