import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent
from ..models.reconciliation import Settlement, ReconciliationRun
from ..models.alert import Alert
from ..models.incident import Incident
from ..models.bank_statement import BankStatementEntry
from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus

logger = logging.getLogger("bomipay")

_ALL_EVENT_TYPES = {
    "transaction_created",
    "settlement_received",
    "incident_created",
    "bank_statement_entry_matched",
    "alert_triggered",
    "sync_job_completed",
    "sync_job_failed",
    "reconciliation_run",
}


class TimelineService:
    @staticmethod
    async def get_payment_timeline(
        db: AsyncSession,
        merchant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        event_types: Optional[set] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        events: list[dict] = []
        wanted = event_types or _ALL_EVENT_TYPES

        # Transactions
        if "transaction_created" in wanted:
            txn_stmt = select(Transaction).where(Transaction.merchant_id == merchant_id)
            if date_from:
                txn_stmt = txn_stmt.where(Transaction.created_at >= date_from)
            if date_to:
                txn_stmt = txn_stmt.where(Transaction.created_at <= date_to)
            if status:
                txn_stmt = txn_stmt.where(Transaction.status == status)
            if provider:
                txn_stmt = txn_stmt.where(Transaction.provider_name == provider)
            txn_stmt = txn_stmt.order_by(Transaction.created_at.desc()).limit(limit)
            txn_result = await db.execute(txn_stmt)
            for t in txn_result.scalars().all():
                events.append({
                    "event_type": "transaction_created",
                    "timestamp": t.created_at.isoformat() if t.created_at else None,
                    "entity_type": "transaction",
                    "entity_id": str(t.id),
                    "summary": f"{t.status} transaction of {t.amount} {t.currency} via {t.provider_name}",
                    "metadata": {
                        "provider": t.provider_name,
                        "status": t.status,
                        "amount_minor": t.amount,
                        "currency": t.currency,
                    },
                })

        # Settlements
        if "settlement_received" in wanted:
            settle_stmt = select(Settlement).where(Settlement.merchant_id == merchant_id)
            if date_from:
                settle_stmt = settle_stmt.where(Settlement.settled_at >= date_from)
            if date_to:
                settle_stmt = settle_stmt.where(Settlement.settled_at <= date_to)
            if provider:
                settle_stmt = settle_stmt.where(Settlement.provider_name == provider)
            settle_result = await db.execute(settle_stmt.limit(limit))
            for s in settle_result.scalars().all():
                events.append({
                    "event_type": "settlement_received",
                    "timestamp": s.settled_at.isoformat() if s.settled_at else None,
                    "entity_type": "settlement",
                    "entity_id": str(s.id),
                    "summary": f"Settlement of {s.amount} {s.currency} from {s.provider_name}",
                    "metadata": {
                        "provider": s.provider_name,
                        "amount_minor": s.amount,
                        "currency": s.currency,
                    },
                })

        # Incidents
        if "incident_created" in wanted:
            incident_stmt = select(Incident).where(Incident.merchant_id == merchant_id)
            if date_from:
                incident_stmt = incident_stmt.where(Incident.created_at >= date_from)
            if date_to:
                incident_stmt = incident_stmt.where(Incident.created_at <= date_to)
            incident_result = await db.execute(incident_stmt.limit(limit))
            for i in incident_result.scalars().all():
                events.append({
                    "event_type": "incident_created",
                    "timestamp": i.created_at.isoformat() if i.created_at else None,
                    "entity_type": "incident",
                    "entity_id": str(i.id),
                    "summary": i.title,
                    "metadata": {
                        "severity": i.severity,
                        "status": i.status,
                    },
                })

        # Bank statement entries
        if "bank_statement_entry_matched" in wanted:
            bse_stmt = (
                select(BankStatementEntry)
                .where(BankStatementEntry.merchant_id == merchant_id)
            )
            if date_from:
                bse_stmt = bse_stmt.where(BankStatementEntry.entry_date >= date_from)
            if date_to:
                bse_stmt = bse_stmt.where(BankStatementEntry.entry_date <= date_to)
            bse_result = await db.execute(bse_stmt.limit(limit))
            for e in bse_result.scalars().all():
                events.append({
                    "event_type": "bank_statement_entry_matched",
                    "timestamp": e.entry_date.isoformat() if e.entry_date else None,
                    "entity_type": "bank_statement_entry",
                    "entity_id": str(e.id),
                    "summary": e.description,
                    "metadata": {
                        "credit_amount_minor": e.credit_amount_minor,
                        "debit_amount_minor": e.debit_amount_minor,
                        "currency": e.currency,
                    },
                })

        # Alerts
        if "alert_triggered" in wanted:
            alert_stmt = select(Alert).where(Alert.merchant_id == merchant_id)
            if date_from:
                alert_stmt = alert_stmt.where(Alert.created_at >= date_from)
            if date_to:
                alert_stmt = alert_stmt.where(Alert.created_at <= date_to)
            alert_result = await db.execute(alert_stmt.limit(limit))
            for a in alert_result.scalars().all():
                events.append({
                    "event_type": "alert_triggered",
                    "timestamp": a.created_at.isoformat() if a.created_at else None,
                    "entity_type": "alert",
                    "entity_id": str(a.id),
                    "summary": a.description,
                    "metadata": {
                        "alert_type": a.alert_type,
                        "severity": a.severity,
                        "status": a.status,
                    },
                })

        # Provider sync jobs
        sync_wanted = wanted & {"sync_job_completed", "sync_job_failed"}
        if sync_wanted:
            sync_stmt = select(ProviderSyncJob).where(ProviderSyncJob.merchant_id == merchant_id)
            if date_from:
                sync_stmt = sync_stmt.where(ProviderSyncJob.created_at >= date_from)
            if date_to:
                sync_stmt = sync_stmt.where(ProviderSyncJob.created_at <= date_to)
            sync_result = await db.execute(sync_stmt.limit(limit))
            for j in sync_result.scalars().all():
                is_failed = j.status in (
                    ProviderSyncStatus.failed.value,
                    ProviderSyncStatus.failed_permanent.value,
                )
                etype = "sync_job_failed" if is_failed else "sync_job_completed"
                if etype not in wanted:
                    continue
                events.append({
                    "event_type": etype,
                    "timestamp": j.created_at.isoformat() if j.created_at else None,
                    "entity_type": "provider_sync_job",
                    "entity_id": str(j.id),
                    "summary": f"Sync job {j.sync_type} {j.status}",
                    "metadata": {
                        "sync_type": j.sync_type,
                        "status": j.status,
                        "records_seen": j.records_seen,
                        "records_created": j.records_created,
                    },
                })

        # Reconciliation runs
        if "reconciliation_run" in wanted:
            recon_stmt = select(ReconciliationRun).where(ReconciliationRun.merchant_id == merchant_id)
            if date_from:
                recon_stmt = recon_stmt.where(ReconciliationRun.created_at >= date_from)
            if date_to:
                recon_stmt = recon_stmt.where(ReconciliationRun.created_at <= date_to)
            recon_result = await db.execute(recon_stmt.limit(limit))
            for r in recon_result.scalars().all():
                events.append({
                    "event_type": "reconciliation_run",
                    "timestamp": r.created_at.isoformat() if r.created_at else None,
                    "entity_type": "reconciliation_run",
                    "entity_id": str(r.id),
                    "summary": f"Reconciliation run {r.status}",
                    "metadata": {
                        "status": str(r.status),
                        "run_name": r.run_name,
                    },
                })

        events.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return events[skip: skip + limit]

    @staticmethod
    async def get_transaction_lifecycle(
        db: AsyncSession,
        merchant_id: str,
        transaction_id: str,
    ) -> Optional[list[dict]]:
        """Return ordered lifecycle events for a single transaction.

        Returns None if the transaction does not exist for the given merchant.
        """
        txn_stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.merchant_id == merchant_id,
        )
        txn_result = await db.execute(txn_stmt)
        txn = txn_result.scalar_one_or_none()
        if txn is None:
            return None

        lifecycle: list[dict] = [{
            "event_type": "transaction_created",
            "timestamp": txn.created_at.isoformat() if txn.created_at else None,
            "entity_type": "transaction",
            "entity_id": str(txn.id),
            "summary": f"Transaction created: {txn.status} {txn.amount} {txn.currency} via {txn.provider_name}",
            "metadata": {
                "status": txn.status,
                "amount_minor": txn.amount,
                "currency": txn.currency,
                "provider": txn.provider_name,
            },
        }]

        events_stmt = (
            select(TransactionEvent)
            .where(TransactionEvent.transaction_id == transaction_id)
            .order_by(TransactionEvent.created_at.asc())
        )
        events_result = await db.execute(events_stmt)
        for e in events_result.scalars().all():
            lifecycle.append({
                "event_type": e.event_type,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
                "entity_type": "transaction_event",
                "entity_id": str(e.id),
                "summary": f"Provider event: {e.event_type} from {e.provider_name}",
                "metadata": {
                    "provider_name": e.provider_name,
                    "provider_event_id": e.provider_event_id,
                    "status": e.status,
                },
            })

        lifecycle.sort(key=lambda x: x.get("timestamp") or "")
        return lifecycle

    @staticmethod
    async def get_timeline_summary(
        db: AsyncSession,
        merchant_id: str,
        days: int = 30,
    ) -> dict:
        """Return event counts per event_type over the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        summary: dict[str, int] = {t: 0 for t in _ALL_EVENT_TYPES}

        # Transactions
        txn_result = await db.execute(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.created_at >= cutoff,
            )
        )
        summary["transaction_created"] = len(txn_result.scalars().all())

        # Settlements
        settle_result = await db.execute(
            select(Settlement).where(
                Settlement.merchant_id == merchant_id,
                Settlement.settled_at >= cutoff,
            )
        )
        summary["settlement_received"] = len(settle_result.scalars().all())

        # Incidents
        incident_result = await db.execute(
            select(Incident).where(
                Incident.merchant_id == merchant_id,
                Incident.created_at >= cutoff,
            )
        )
        summary["incident_created"] = len(incident_result.scalars().all())

        # Bank statement entries
        bse_result = await db.execute(
            select(BankStatementEntry).where(
                BankStatementEntry.merchant_id == merchant_id,
                BankStatementEntry.entry_date >= cutoff,
            )
        )
        summary["bank_statement_entry_matched"] = len(bse_result.scalars().all())

        # Alerts
        alert_result = await db.execute(
            select(Alert).where(
                Alert.merchant_id == merchant_id,
                Alert.created_at >= cutoff,
            )
        )
        summary["alert_triggered"] = len(alert_result.scalars().all())

        # Provider sync jobs — split by outcome
        sync_result = await db.execute(
            select(ProviderSyncJob).where(
                ProviderSyncJob.merchant_id == merchant_id,
                ProviderSyncJob.created_at >= cutoff,
            )
        )
        for j in sync_result.scalars().all():
            is_failed = j.status in (
                ProviderSyncStatus.failed.value,
                ProviderSyncStatus.failed_permanent.value,
            )
            if is_failed:
                summary["sync_job_failed"] += 1
            else:
                summary["sync_job_completed"] += 1

        # Reconciliation runs
        recon_result = await db.execute(
            select(ReconciliationRun).where(
                ReconciliationRun.merchant_id == merchant_id,
                ReconciliationRun.created_at >= cutoff,
            )
        )
        summary["reconciliation_run"] = len(recon_result.scalars().all())

        return summary
