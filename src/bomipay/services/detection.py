from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .alert import AlertService
from ..models.alert import AlertSeverity, AlertType
from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent


class FailureDetectionService:
    FAILURE_SPIKE_WINDOW_MINUTES = 10
    FAILURE_SPIKE_THRESHOLD = 3
    TIMEOUT_WINDOW_MINUTES = 30
    TIMEOUT_THRESHOLD = 2
    TIMEOUT_KEYWORDS = {
        "timeout",
        "timed out",
        "timedout",
        "gateway timeout",
        "connection reset",
        "request timeout",
    }

    @staticmethod
    async def evaluate_event(db: AsyncSession, transaction: Transaction, event: TransactionEvent):
        if event.status == TransactionStatus.failed.value:
            await AlertService.create_alert(
                db=db,
                merchant_id=transaction.merchant_id,
                alert_type=AlertType.transaction_failure,
                severity=AlertSeverity.high,
                description=f"Transaction {transaction.provider_transaction_id} failed for provider {event.provider_name}.",
                transaction_id=transaction.id,
                source_event_id=event.provider_event_id,
                metadata_json={
                    "provider_name": event.provider_name,
                    "status_reason": transaction.status_reason,
                    "event_type": event.event_type,
                },
            )

        await FailureDetectionService._evaluate_failure_spike(db, transaction, event)
        await FailureDetectionService._evaluate_timeout_pattern(db, transaction, event)
        await FailureDetectionService._evaluate_error_pattern(db, transaction, event)

    @staticmethod
    async def _evaluate_failure_spike(db: AsyncSession, transaction: Transaction, event: TransactionEvent):
        window_start = datetime.now(timezone.utc) - timedelta(minutes=FailureDetectionService.FAILURE_SPIKE_WINDOW_MINUTES)
        result = await db.execute(
            select(func.count(TransactionEvent.id))
            .join(Transaction, TransactionEvent.transaction_id == Transaction.id)
            .where(Transaction.merchant_id == transaction.merchant_id)
            .where(TransactionEvent.provider_name == transaction.provider_name)
            .where(TransactionEvent.status == TransactionStatus.failed.value)
            .where(TransactionEvent.created_at >= window_start)
        )
        count = result.scalar_one()
        if count >= FailureDetectionService.FAILURE_SPIKE_THRESHOLD:
            source_event_id = f"failure_spike:{transaction.provider_name}:{window_start.strftime('%Y%m%d%H%M')}"
            await AlertService.create_alert(
                db=db,
                merchant_id=transaction.merchant_id,
                alert_type=AlertType.provider_error,
                severity=AlertSeverity.critical,
                description=(
                    f"Provider {transaction.provider_name} has {count} failed transaction events in the last "
                    f"{FailureDetectionService.FAILURE_SPIKE_WINDOW_MINUTES} minutes."
                ),
                source_event_id=source_event_id,
                metadata_json={
                    "provider_name": transaction.provider_name,
                    "failure_count": count,
                    "window_minutes": FailureDetectionService.FAILURE_SPIKE_WINDOW_MINUTES,
                },
            )

    @staticmethod
    async def _evaluate_timeout_pattern(db: AsyncSession, transaction: Transaction, event: TransactionEvent):
        reason = (transaction.status_reason or "").lower()
        if not any(keyword in reason for keyword in FailureDetectionService.TIMEOUT_KEYWORDS):
            return

        window_start = datetime.utcnow() - timedelta(minutes=FailureDetectionService.TIMEOUT_WINDOW_MINUTES)
        result = await db.execute(
            select(func.count(TransactionEvent.id))
            .join(Transaction, TransactionEvent.transaction_id == Transaction.id)
            .where(Transaction.merchant_id == transaction.merchant_id)
            .where(TransactionEvent.provider_name == transaction.provider_name)
            .where(TransactionEvent.status == TransactionStatus.failed.value)
            .where(TransactionEvent.status_reason.ilike("%timeout%"))
            .where(TransactionEvent.created_at >= window_start)
        )
        count = result.scalar_one()
        if count >= FailureDetectionService.TIMEOUT_THRESHOLD:
            source_event_id = f"timeout_pattern:{transaction.provider_name}:{window_start.strftime('%Y%m%d%H%M')}"
            await AlertService.create_alert(
                db=db,
                merchant_id=transaction.merchant_id,
                alert_type=AlertType.provider_error,
                severity=AlertSeverity.high,
                description=(
                    f"Repeated timeout failures detected for provider {transaction.provider_name}. "
                    f"{count} timeout events in the last {FailureDetectionService.TIMEOUT_WINDOW_MINUTES} minutes."
                ),
                source_event_id=source_event_id,
                metadata_json={
                    "provider_name": transaction.provider_name,
                    "timeout_count": count,
                    "window_minutes": FailureDetectionService.TIMEOUT_WINDOW_MINUTES,
                },
            )

    @staticmethod
    async def _evaluate_error_pattern(db: AsyncSession, transaction: Transaction, event: TransactionEvent):
        reason = (transaction.status_reason or "").lower()
        if "reversal" in reason or "chargeback" in reason or "dispute" in reason:
            source_event_id = f"reversal_pattern:{transaction.provider_name}:{event.provider_event_id}"
            await AlertService.create_alert(
                db=db,
                merchant_id=transaction.merchant_id,
                alert_type=AlertType.provider_error,
                severity=AlertSeverity.high,
                description=(
                    f"Payment reversal or dispute pattern detected for transaction {transaction.provider_transaction_id}."
                ),
                transaction_id=transaction.id,
                source_event_id=source_event_id,
                metadata_json={
                    "provider_name": transaction.provider_name,
                    "status_reason": transaction.status_reason,
                },
            )


class HangingTransactionDetector:
    PENDING_HANGING_MINUTES = 30
    SUCCESS_NOT_SETTLED_HOURS = 24

    @staticmethod
    def _normalize_timestamp(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    async def evaluate_transaction(db: AsyncSession, transaction: Transaction):
        now = datetime.now(timezone.utc)
        initiated_at = HangingTransactionDetector._normalize_timestamp(transaction.initiated_at)
        if transaction.status == TransactionStatus.pending.value and initiated_at:
            threshold = now - timedelta(minutes=HangingTransactionDetector.PENDING_HANGING_MINUTES)
            if initiated_at < threshold:
                source_event_id = f"hanging_transaction:{transaction.id}"
                await AlertService.create_alert(
                    db=db,
                    merchant_id=transaction.merchant_id,
                    alert_type=AlertType.hanging_payment,
                    severity=AlertSeverity.medium,
                    description=(
                        f"Transaction {transaction.provider_transaction_id} has been pending for over "
                        f"{HangingTransactionDetector.PENDING_HANGING_MINUTES} minutes."
                    ),
                    transaction_id=transaction.id,
                    source_event_id=source_event_id,
                    metadata_json={
                        "pending_minutes": HangingTransactionDetector.PENDING_HANGING_MINUTES,
                    },
                )

        if transaction.status == TransactionStatus.success.value and not transaction.settled_at:
            reference_time = HangingTransactionDetector._normalize_timestamp(transaction.confirmed_at or transaction.initiated_at)
            if reference_time:
                threshold = now - timedelta(hours=HangingTransactionDetector.SUCCESS_NOT_SETTLED_HOURS)
                if reference_time < threshold:
                    source_event_id = f"successful_not_settled:{transaction.id}"
                    await AlertService.create_alert(
                        db=db,
                        merchant_id=transaction.merchant_id,
                        alert_type=AlertType.hanging_payment,
                        severity=AlertSeverity.medium,
                        description=(
                            f"Transaction {transaction.provider_transaction_id} succeeded but has not settled after "
                            f"{HangingTransactionDetector.SUCCESS_NOT_SETTLED_HOURS} hours."
                        ),
                        transaction_id=transaction.id,
                        source_event_id=source_event_id,
                        metadata_json={
                            "confirmed_at": transaction.confirmed_at.isoformat() if transaction.confirmed_at else None,
                        },
                    )

    @staticmethod
    async def scan_merchant_transactions(db: AsyncSession, merchant_id):
        result = await db.execute(select(Transaction).where(Transaction.merchant_id == merchant_id))
        transactions = result.scalars().all()
        alerts = []
        for transaction in transactions:
            await HangingTransactionDetector.evaluate_transaction(db, transaction)
        return alerts
