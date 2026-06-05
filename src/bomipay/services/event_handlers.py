import traceback
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy import select, update

from ..db import AsyncSessionLocal
from ..models.alert import Alert, AlertSeverity, AlertType, AlertStatus
from ..models.audit import AuditLog
from ..models.dashboard import DashboardSnapshot, DashboardSnapshotStatus
from ..models.data_source import DataSource
from ..models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from ..models.money_at_risk import MoneyAtRisk
from ..models.notification import Notification, NotificationChannel, NotificationStatus
from ..models.provider_health import ProviderHealthMetrics
from ..models.reconciliation import Settlement
from ..models.transaction import Transaction

logger = logging.getLogger("bomipay")

# Transactions above this amount (in minor currency units, e.g. cents) trigger a risk alert.
RISK_THRESHOLD_MINOR = 1_000_000  # 10,000.00 in a 2-decimal currency


class EventHandlers:
    """
    Event handlers for different domain events.
    Each handler receives the event payload and processes it.
    """

    HANDLERS = {}

    @classmethod
    def register_handler(cls, event_type: str) -> Callable:
        """Decorator to register event handlers."""
        def decorator(func: Callable) -> Callable:
            cls.HANDLERS[event_type] = func
            return func
        return decorator

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @staticmethod
    async def handle_transaction_created(payload: dict):
        """Handle transaction.created event."""
        transaction_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.info(
            "Handling transaction.created",
            extra={"transaction_id": transaction_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="transaction.created",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Risk threshold check
                amount = payload.get("amount", 0)
                if merchant_id and amount and amount >= RISK_THRESHOLD_MINOR:
                    db.add(Alert(
                        merchant_id=merchant_id,
                        transaction_id=transaction_id,
                        alert_type=AlertType.transaction_failure.value,
                        severity=AlertSeverity.high.value,
                        status=AlertStatus.open.value,
                        description=(
                            f"High-value transaction detected: "
                            f"amount={amount}, transaction_id={transaction_id}"
                        ),
                        source_event_id=str(payload.get("event_id", "")),
                        source_type="transaction",
                    ))

                # Update data source last_sync_at
                provider_name = payload.get("provider_name")
                if merchant_id and provider_name:
                    await db.execute(
                        update(DataSource)
                        .where(DataSource.merchant_id == merchant_id)
                        .where(DataSource.provider_name == provider_name)
                        .values(last_sync_at=EventHandlers._now())
                    )

    @staticmethod
    async def handle_transaction_updated(payload: dict):
        """Handle transaction.updated event."""
        transaction_id = payload.get("aggregate_id")
        logger.info(
            "Handling transaction.updated",
            extra={"transaction_id": transaction_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="transaction.updated",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Increment provider health failure count when status → failed
                new_status = payload.get("status") or payload.get("new_status")
                if new_status == "failed":
                    merchant_id = payload.get("merchant_id")
                    provider_name = payload.get("provider_name")
                    if merchant_id and provider_name:
                        today = date.today()
                        result = await db.execute(
                            select(ProviderHealthMetrics)
                            .where(ProviderHealthMetrics.merchant_id == merchant_id)
                            .where(ProviderHealthMetrics.provider_name == provider_name)
                            .where(ProviderHealthMetrics.metric_date == today)
                        )
                        metrics = result.scalars().first()
                        if metrics:
                            metrics.transaction_fail_count += 1
                        else:
                            db.add(ProviderHealthMetrics(
                                merchant_id=merchant_id,
                                provider_name=provider_name,
                                metric_date=today,
                                transaction_fail_count=1,
                            ))

    @staticmethod
    async def handle_transaction_settled(payload: dict):
        """Handle transaction.settled event."""
        logger.info(
            "Handling transaction.settled",
            extra={"transaction_id": payload.get("aggregate_id")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="transaction.settled",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_settlement_received(payload: dict):
        """Handle settlement.received event."""
        settlement_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.info(
            "Handling settlement.received",
            extra={"settlement_id": settlement_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="settlement.received",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Upsert Settlement record
                provider_name = payload.get("provider_name", "")
                settlement_reference = payload.get("settlement_reference") or str(settlement_id or uuid.uuid4())
                amount = payload.get("amount", 0)
                currency = payload.get("currency", "")
                settled_at_raw = payload.get("settled_at")
                settled_at = (
                    datetime.fromisoformat(settled_at_raw)
                    if settled_at_raw
                    else EventHandlers._now()
                )

                if merchant_id:
                    result = await db.execute(
                        select(Settlement)
                        .where(Settlement.merchant_id == merchant_id)
                        .where(Settlement.settlement_reference == settlement_reference)
                    )
                    settlement = result.scalars().first()
                    if settlement is None:
                        db.add(Settlement(
                            merchant_id=merchant_id,
                            provider_name=provider_name,
                            settlement_reference=settlement_reference,
                            amount=amount,
                            currency=currency,
                            settled_at=settled_at,
                            metadata_json=payload,
                        ))

                    # Trigger money-at-risk recalculation: upsert today's MAR record
                    today = date.today()
                    result = await db.execute(
                        select(MoneyAtRisk)
                        .where(MoneyAtRisk.merchant_id == merchant_id)
                        .where(MoneyAtRisk.period_date == today)
                    )
                    mar = result.scalars().first()
                    if mar is None:
                        db.add(MoneyAtRisk(
                            merchant_id=merchant_id,
                            period_date=today,
                        ))

    @staticmethod
    async def handle_settlement_mismatch_detected(payload: dict):
        """Handle settlement.mismatch_detected event."""
        logger.warning(
            "Handling settlement.mismatch_detected",
            extra={
                "settlement_id": payload.get("aggregate_id"),
                "merchant_id": payload.get("merchant_id"),
            },
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="settlement.mismatch_detected",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_reconciliation_completed(payload: dict):
        """Handle reconciliation.completed event."""
        recon_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.info(
            "Handling reconciliation.completed",
            extra={"reconciliation_id": recon_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="reconciliation.completed",
                    event_payload=payload,
                    source="event_bus",
                ))

                unmatched_count = payload.get("unmatched_count", 0)

                # Create incident if unmatched transactions exist
                if merchant_id and unmatched_count and unmatched_count > 0:
                    db.add(Incident(
                        merchant_id=merchant_id,
                        title=f"Reconciliation completed with {unmatched_count} unmatched transaction(s)",
                        incident_type=IncidentType.reconciliation_mismatch.value,
                        severity=IncidentSeverity.medium.value,
                        status=IncidentStatus.open.value,
                        started_at=EventHandlers._now(),
                        summary=(
                            f"Reconciliation run {recon_id} completed. "
                            f"{unmatched_count} transaction(s) remain unmatched."
                        ),
                        affected_transaction_count=unmatched_count,
                    ))

                # Update (or create) dashboard snapshot
                if merchant_id:
                    now = EventHandlers._now()
                    db.add(DashboardSnapshot(
                        merchant_id=merchant_id,
                        snapshot_time=now,
                        reconciliation_mismatches_count=unmatched_count or 0,
                        status=DashboardSnapshotStatus.active.value,
                    ))

    @staticmethod
    async def handle_reconciliation_mismatch(payload: dict):
        """Handle reconciliation.mismatch event."""
        logger.warning(
            "Handling reconciliation.mismatch",
            extra={"reconciliation_id": payload.get("aggregate_id")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="reconciliation.mismatch",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_incident_created(payload: dict):
        """Handle incident.created event."""
        incident_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.warning(
            "Handling incident.created",
            extra={"incident_id": incident_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="incident.created",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Create in-app notification for merchant
                if merchant_id:
                    title = payload.get("title", "A new incident has been created")
                    severity = payload.get("severity", "medium")
                    db.add(Notification(
                        merchant_id=merchant_id,
                        channel=NotificationChannel.in_app.value,
                        message=f"[{severity.upper()}] Incident created: {title}",
                        status=NotificationStatus.unread.value,
                        metadata_json={"incident_id": str(incident_id)},
                    ))

    @staticmethod
    async def handle_incident_acknowledged(payload: dict):
        """Handle incident.acknowledged event."""
        logger.info(
            "Handling incident.acknowledged",
            extra={"incident_id": payload.get("aggregate_id")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="incident.acknowledged",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_incident_resolved(payload: dict):
        """Handle incident.resolved event."""
        logger.info(
            "Handling incident.resolved",
            extra={"incident_id": payload.get("aggregate_id")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="incident.resolved",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_alert_created(payload: dict):
        """Handle alert.created event."""
        alert_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.info(
            "Handling alert.created",
            extra={"alert_id": alert_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="alert.created",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Create in-app notification for merchant
                if merchant_id:
                    alert_type = payload.get("alert_type", "alert")
                    description = payload.get("description", "A new alert has been raised")
                    db.add(Notification(
                        merchant_id=merchant_id,
                        channel=NotificationChannel.in_app.value,
                        message=f"[ALERT] {alert_type}: {description}",
                        status=NotificationStatus.unread.value,
                        metadata_json={"alert_id": str(alert_id)},
                    ))

    @staticmethod
    async def handle_alert_resolved(payload: dict):
        """Handle alert.resolved event."""
        logger.info(
            "Handling alert.resolved",
            extra={"alert_id": payload.get("aggregate_id")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="alert.resolved",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_dispute_created(payload: dict):
        """Handle dispute.created event."""
        dispute_id = payload.get("aggregate_id")
        merchant_id = payload.get("merchant_id")
        logger.warning(
            "Handling dispute.created",
            extra={"dispute_id": dispute_id, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="dispute.created",
                    event_payload=payload,
                    source="event_bus",
                ))

                # Update transaction status to "disputed"
                transaction_id = payload.get("transaction_id") or payload.get("aggregate_id")
                if transaction_id:
                    await db.execute(
                        update(Transaction)
                        .where(Transaction.id == transaction_id)
                        .values(status="disputed")
                    )

    @staticmethod
    async def handle_provider_sync_completed(payload: dict):
        """Handle provider.sync.completed event."""
        provider_name = payload.get("provider") or payload.get("provider_name")
        merchant_id = payload.get("merchant_id")
        logger.info(
            "Handling provider.sync.completed",
            extra={"provider": provider_name, "merchant_id": merchant_id},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Audit log
                db.add(AuditLog(
                    event_type="provider.sync.completed",
                    event_payload=payload,
                    source="event_bus",
                ))

                now = EventHandlers._now()

                # Update provider health last_sync_at (metric_date bucket)
                if merchant_id and provider_name:
                    today = date.today()
                    result = await db.execute(
                        select(ProviderHealthMetrics)
                        .where(ProviderHealthMetrics.merchant_id == merchant_id)
                        .where(ProviderHealthMetrics.provider_name == provider_name)
                        .where(ProviderHealthMetrics.metric_date == today)
                    )
                    metrics = result.scalars().first()
                    if metrics is None:
                        db.add(ProviderHealthMetrics(
                            merchant_id=merchant_id,
                            provider_name=provider_name,
                            metric_date=today,
                        ))

                # Update data source last_sync_at and last_success_at
                if merchant_id and provider_name:
                    await db.execute(
                        update(DataSource)
                        .where(DataSource.merchant_id == merchant_id)
                        .where(DataSource.provider_name == provider_name)
                        .values(last_sync_at=now, last_success_at=now)
                    )

    @staticmethod
    async def handle_provider_sync_failed(payload: dict):
        """Handle provider.sync.failed event."""
        logger.error(
            "Handling provider.sync.failed",
            extra={
                "provider": payload.get("provider"),
                "merchant_id": payload.get("merchant_id"),
                "error": payload.get("error"),
            },
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="provider.sync.failed",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_webhook_received(payload: dict):
        """Handle webhook.received event."""
        logger.info(
            "Handling webhook.received",
            extra={
                "provider": payload.get("provider"),
                "event_type": payload.get("webhook_event_type"),
            },
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="webhook.received",
                    event_payload=payload,
                    source="event_bus",
                ))

    @staticmethod
    async def handle_webhook_processed(payload: dict):
        """Handle webhook.processed event."""
        logger.info(
            "Handling webhook.processed",
            extra={"provider": payload.get("provider")},
        )
        async with AsyncSessionLocal() as db:
            async with db.begin():
                db.add(AuditLog(
                    event_type="webhook.processed",
                    event_payload=payload,
                    source="event_bus",
                ))

    @classmethod
    async def handle_event(cls, event_type: str, payload: dict):
        """
        Dispatch event to appropriate handler.
        Failed handlers are dead-lettered: the error is logged with full context
        (event_type, payload, traceback) and the exception is NOT re-raised so
        the worker continues processing subsequent events.

        Args:
            event_type: Type of event
            payload: Event payload
        """
        handler = cls.HANDLERS.get(event_type)
        if handler:
            try:
                await handler(payload)
            except Exception as exc:
                # Dead-letter: log the failure but do not crash the worker.
                logger.error(
                    "dead_letter | handler failed — event dropped to error log",
                    extra={
                        "event_type": event_type,
                        "payload": payload,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
        else:
            logger.warning(f"No handler registered for event type: {event_type}")


# Register all handlers
EventHandlers.HANDLERS = {
    "transaction.created": EventHandlers.handle_transaction_created,
    "transaction.updated": EventHandlers.handle_transaction_updated,
    "transaction.settled": EventHandlers.handle_transaction_settled,
    "settlement.received": EventHandlers.handle_settlement_received,
    "settlement.mismatch_detected": EventHandlers.handle_settlement_mismatch_detected,
    "reconciliation.completed": EventHandlers.handle_reconciliation_completed,
    "reconciliation.mismatch": EventHandlers.handle_reconciliation_mismatch,
    "incident.created": EventHandlers.handle_incident_created,
    "incident.acknowledged": EventHandlers.handle_incident_acknowledged,
    "incident.resolved": EventHandlers.handle_incident_resolved,
    "alert.created": EventHandlers.handle_alert_created,
    "alert.resolved": EventHandlers.handle_alert_resolved,
    "dispute.created": EventHandlers.handle_dispute_created,
    "provider.sync.completed": EventHandlers.handle_provider_sync_completed,
    "provider.sync.failed": EventHandlers.handle_provider_sync_failed,
    "webhook.received": EventHandlers.handle_webhook_received,
    "webhook.processed": EventHandlers.handle_webhook_processed,
}
