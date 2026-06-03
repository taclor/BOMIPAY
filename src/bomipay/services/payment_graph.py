import logging
import uuid as _uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction
from ..models.transaction_event import TransactionEvent
from ..models.reconciliation import ReconciliationResult, Settlement
from ..models.incident import Incident
from ..models.alert import Alert
from ..models.bank_statement import BankStatementEntry
from ..models.provider_account import ProviderAccount
from ..models.provider_sync_job import ProviderSyncJob
from ..models.data_source import DataSource

logger = logging.getLogger("bomipay")


class PaymentGraphService:
    @staticmethod
    async def get_transaction_graph(db: AsyncSession, merchant_id: str, transaction_id: str) -> dict:
        txn_result = await db.execute(
            select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.merchant_id == merchant_id,
            )
        )
        txn = txn_result.scalar_one_or_none()
        if txn is None:
            return None

        nodes = [{
            "id": str(txn.id),
            "type": "transaction",
            "label": f"Transaction {txn.provider_transaction_id}",
            "status": txn.status,
            "amount_minor": txn.amount,
            "currency": txn.currency,
            "provider": txn.provider_name,
        }]
        edges = []

        # Transaction events
        events_result = await db.execute(
            select(TransactionEvent).where(TransactionEvent.transaction_id == transaction_id)
        )
        for ev in events_result.scalars().all():
            nodes.append({
                "id": str(ev.id),
                "type": "transaction_event",
                "label": f"Event: {ev.event_type}",
                "event_type": ev.event_type,
            })
            edges.append({"from": str(txn.id), "to": str(ev.id), "relationship": "has_event"})

        # Reconciliation results
        recon_result = await db.execute(
            select(ReconciliationResult).where(ReconciliationResult.transaction_id == transaction_id)
        )
        for rr in recon_result.scalars().all():
            nodes.append({
                "id": str(rr.id),
                "type": "reconciliation_result",
                "label": f"Reconciliation: {rr.match_status}",
                "match_status": rr.match_status,
            })
            edges.append({"from": str(txn.id), "to": str(rr.id), "relationship": "reconciled_as"})

        # Bank statement entries matched by amount
        bse_result = await db.execute(
            select(BankStatementEntry).where(
                BankStatementEntry.merchant_id == merchant_id,
                or_(
                    BankStatementEntry.credit_amount_minor == txn.amount,
                    BankStatementEntry.debit_amount_minor == txn.amount,
                ),
            ).limit(5)
        )
        for bse in bse_result.scalars().all():
            nodes.append({
                "id": str(bse.id),
                "type": "bank_statement_entry",
                "label": f"Bank Entry: {bse.description[:50]}",
                "credit_amount_minor": bse.credit_amount_minor,
                "debit_amount_minor": bse.debit_amount_minor,
            })
            edges.append({"from": str(txn.id), "to": str(bse.id), "relationship": "matched_bank_entry"})

        # Settlements linked by provider
        provider_settle_result = await db.execute(
            select(Settlement).where(
                Settlement.merchant_id == merchant_id,
                Settlement.provider_name == txn.provider_name,
            ).limit(3)
        )
        for s in provider_settle_result.scalars().all():
            nodes.append({
                "id": str(s.id),
                "type": "settlement",
                "label": f"Settlement {s.settlement_reference}",
                "amount_minor": s.amount,
                "provider": s.provider_name,
            })
            edges.append({"from": str(txn.id), "to": str(s.id), "relationship": "settled_via"})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_incident_graph(db: AsyncSession, merchant_id: str, incident_id: str) -> dict:
        incident_result = await db.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.merchant_id == merchant_id,
            )
        )
        incident = incident_result.scalar_one_or_none()
        if incident is None:
            return None

        nodes = [{
            "id": str(incident.id),
            "type": "incident",
            "label": incident.title,
            "severity": incident.severity,
            "status": incident.status,
        }]
        edges = []

        # Alerts related by provider and merchant
        if incident.provider_name:
            alerts_result = await db.execute(
                select(Alert).where(
                    Alert.merchant_id == merchant_id,
                    Alert.metadata_json.is_not(None),
                ).limit(10)
            )
            for a in alerts_result.scalars().all():
                nodes.append({
                    "id": str(a.id),
                    "type": "alert",
                    "label": f"Alert: {a.alert_type}",
                    "severity": a.severity,
                })
                edges.append({"from": str(a.id), "to": str(incident.id), "relationship": "escalated_to"})

        # Affected transactions via related_transaction_ids JSON field (if present)
        related_txn_ids = getattr(incident, "related_transaction_ids", None)
        if related_txn_ids:
            try:
                if isinstance(related_txn_ids, str):
                    import json
                    related_txn_ids = json.loads(related_txn_ids)
                valid_ids = [str(_uuid.UUID(str(tid))) for tid in related_txn_ids if tid]
            except Exception:
                valid_ids = []
            if valid_ids:
                affected_result = await db.execute(
                    select(Transaction).where(
                        Transaction.id.in_(valid_ids),
                        Transaction.merchant_id == merchant_id,
                    ).limit(10)
                )
                for t in affected_result.scalars().all():
                    nodes.append({
                        "id": str(t.id),
                        "type": "transaction",
                        "label": f"Txn {t.provider_transaction_id}",
                        "status": t.status,
                    })
                    edges.append({"from": str(incident.id), "to": str(t.id), "relationship": "affected_transaction"})

        # Provider sync failures for same merchant
        sync_result = await db.execute(
            select(ProviderSyncJob).where(
                ProviderSyncJob.merchant_id == merchant_id,
                ProviderSyncJob.status.in_(["failed", "failed_permanent"]),
            ).limit(5)
        )
        for job in sync_result.scalars().all():
            nodes.append({
                "id": str(job.id),
                "type": "provider_sync_job",
                "label": f"Sync Failure: {job.sync_type}",
                "sync_type": job.sync_type,
                "status": job.status,
                "error_message": job.error_message,
            })
            edges.append({"from": str(incident.id), "to": str(job.id), "relationship": "related_sync_failure"})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_merchant_overview(db: AsyncSession, merchant_id: str) -> dict:
        nodes = [{"id": merchant_id, "type": "merchant", "label": "Merchant"}]
        edges = []

        # Count transactions
        txns_result = await db.execute(
            select(Transaction).where(Transaction.merchant_id == merchant_id).limit(20)
        )
        for t in txns_result.scalars().all():
            nodes.append({
                "id": str(t.id),
                "type": "transaction",
                "label": f"Txn {t.provider_transaction_id}",
                "status": t.status,
            })
            edges.append({"from": merchant_id, "to": str(t.id), "relationship": "owns"})

        # Settlements
        settle_result = await db.execute(
            select(Settlement).where(Settlement.merchant_id == merchant_id).limit(10)
        )
        for s in settle_result.scalars().all():
            nodes.append({
                "id": str(s.id),
                "type": "settlement",
                "label": f"Settlement {s.settlement_reference}",
                "amount_minor": s.amount,
            })
            edges.append({"from": merchant_id, "to": str(s.id), "relationship": "received_settlement"})

        # Open incidents
        incident_result = await db.execute(
            select(Incident).where(Incident.merchant_id == merchant_id).limit(5)
        )
        for i in incident_result.scalars().all():
            nodes.append({
                "id": str(i.id),
                "type": "incident",
                "label": i.title,
                "status": i.status,
            })
            edges.append({"from": merchant_id, "to": str(i.id), "relationship": "has_incident"})

        # Provider accounts
        pa_result = await db.execute(
            select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id).limit(10)
        )
        for pa in pa_result.scalars().all():
            nodes.append({
                "id": str(pa.id),
                "type": "provider_account",
                "label": f"Provider: {pa.provider_name}",
                "provider_name": pa.provider_name,
                "status": pa.status,
            })
            edges.append({"from": merchant_id, "to": str(pa.id), "relationship": "uses_provider"})

        # Data sources
        ds_result = await db.execute(
            select(DataSource).where(DataSource.merchant_id == merchant_id).limit(10)
        )
        for ds in ds_result.scalars().all():
            nodes.append({
                "id": str(ds.id),
                "type": "data_source",
                "label": ds.display_name,
                "source_type": ds.source_type,
                "status": ds.status,
            })
            edges.append({"from": merchant_id, "to": str(ds.id), "relationship": "has_data_source"})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_settlement_graph(db: AsyncSession, merchant_id: str, settlement_id: str) -> dict | None:
        settle_result = await db.execute(
            select(Settlement).where(
                Settlement.id == settlement_id,
                Settlement.merchant_id == merchant_id,
            )
        )
        settlement = settle_result.scalar_one_or_none()
        if settlement is None:
            return None

        nodes = [{
            "id": str(settlement.id),
            "type": "settlement",
            "label": f"Settlement {settlement.settlement_reference}",
            "amount_minor": settlement.amount,
            "currency": settlement.currency,
            "provider": settlement.provider_name,
            "settled_at": settlement.settled_at.isoformat() if settlement.settled_at else None,
        }]
        edges = []

        # Related transactions by provider + date proximity ±1 day
        date_from = settlement.settled_at - timedelta(days=1)
        date_to = settlement.settled_at + timedelta(days=1)
        txns_result = await db.execute(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.provider_name == settlement.provider_name,
                Transaction.created_at >= date_from,
                Transaction.created_at <= date_to,
            ).limit(15)
        )
        related_txns = txns_result.scalars().all()
        txn_ids = []
        for t in related_txns:
            txn_ids.append(str(t.id))
            nodes.append({
                "id": str(t.id),
                "type": "transaction",
                "label": f"Txn {t.provider_transaction_id}",
                "status": t.status,
                "amount_minor": t.amount,
            })
            edges.append({"from": str(settlement.id), "to": str(t.id), "relationship": "includes_transaction"})

        # Reconciliation results for related transactions
        if txn_ids:
            recon_result = await db.execute(
                select(ReconciliationResult).where(
                    ReconciliationResult.transaction_id.in_(txn_ids),
                ).limit(15)
            )
            for rr in recon_result.scalars().all():
                nodes.append({
                    "id": str(rr.id),
                    "type": "reconciliation_result",
                    "label": f"Reconciliation: {rr.match_status}",
                    "match_status": rr.match_status,
                })
                edges.append({"from": str(settlement.id), "to": str(rr.id), "relationship": "verified_by"})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_customer_graph(db: AsyncSession, merchant_id: str, customer_email: str) -> dict | None:
        """Return graph of all transactions and related entities for a customer within a merchant tenant."""
        txns_result = await db.execute(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.customer_email == customer_email,
            ).limit(20)
        )
        txns = txns_result.scalars().all()
        if not txns:
            return None

        nodes = [{
            "id": customer_email,
            "type": "customer",
            "label": f"Customer: {customer_email}",
        }]
        edges = []

        for txn in txns:
            nodes.append({
                "id": str(txn.id),
                "type": "transaction",
                "label": f"Transaction {txn.provider_transaction_id}",
                "status": txn.status,
                "amount_minor": txn.amount,
                "currency": txn.currency,
                "provider": txn.provider_name,
            })
            edges.append({"from": customer_email, "to": str(txn.id), "relationship": "initiated"})

            # Transaction events
            events_result = await db.execute(
                select(TransactionEvent).where(TransactionEvent.transaction_id == str(txn.id))
            )
            for ev in events_result.scalars().all():
                nodes.append({
                    "id": str(ev.id),
                    "type": "transaction_event",
                    "label": f"Event: {ev.event_type}",
                    "event_type": ev.event_type,
                })
                edges.append({"from": str(txn.id), "to": str(ev.id), "relationship": "has_event"})

            # Reconciliation results
            recon_result = await db.execute(
                select(ReconciliationResult).where(ReconciliationResult.transaction_id == str(txn.id))
            )
            for rr in recon_result.scalars().all():
                nodes.append({
                    "id": str(rr.id),
                    "type": "reconciliation_result",
                    "label": f"Reconciliation: {rr.match_status}",
                    "match_status": rr.match_status,
                })
                edges.append({"from": str(txn.id), "to": str(rr.id), "relationship": "reconciled_as"})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_merchant_network(db: AsyncSession, merchant_id: str) -> dict:
        nodes = [{"id": merchant_id, "type": "merchant", "label": "Merchant"}]
        edges = []

        # Provider accounts
        pa_result = await db.execute(
            select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id).limit(10)
        )
        for pa in pa_result.scalars().all():
            nodes.append({
                "id": str(pa.id),
                "type": "provider_account",
                "label": f"Provider: {pa.provider_name}",
                "provider_name": pa.provider_name,
                "status": pa.status,
            })
            edges.append({"from": merchant_id, "to": str(pa.id), "relationship": "uses_provider"})

        # Data sources
        ds_result = await db.execute(
            select(DataSource).where(DataSource.merchant_id == merchant_id).limit(10)
        )
        for ds in ds_result.scalars().all():
            nodes.append({
                "id": str(ds.id),
                "type": "data_source",
                "label": ds.display_name,
                "source_type": ds.source_type,
                "status": ds.status,
            })
            edges.append({"from": merchant_id, "to": str(ds.id), "relationship": "has_data_source"})

        # Recent transactions
        txns_result = await db.execute(
            select(Transaction).where(Transaction.merchant_id == merchant_id)
            .order_by(Transaction.created_at.desc())
            .limit(15)
        )
        for t in txns_result.scalars().all():
            nodes.append({
                "id": str(t.id),
                "type": "transaction",
                "label": f"Txn {t.provider_transaction_id}",
                "status": t.status,
                "amount_minor": t.amount,
            })
            edges.append({"from": merchant_id, "to": str(t.id), "relationship": "owns"})

        # Recent settlements
        settle_result = await db.execute(
            select(Settlement).where(Settlement.merchant_id == merchant_id)
            .order_by(Settlement.settled_at.desc())
            .limit(10)
        )
        for s in settle_result.scalars().all():
            nodes.append({
                "id": str(s.id),
                "type": "settlement",
                "label": f"Settlement {s.settlement_reference}",
                "amount_minor": s.amount,
                "provider": s.provider_name,
            })
            edges.append({"from": merchant_id, "to": str(s.id), "relationship": "received"})

        # Open incidents
        incident_result = await db.execute(
            select(Incident).where(
                Incident.merchant_id == merchant_id,
                Incident.status == "open",
            ).limit(5)
        )
        for i in incident_result.scalars().all():
            nodes.append({
                "id": str(i.id),
                "type": "incident",
                "label": i.title,
                "severity": i.severity,
                "status": i.status,
            })
            edges.append({"from": merchant_id, "to": str(i.id), "relationship": "has_incident"})

        # Active alerts
        alerts_result = await db.execute(
            select(Alert).where(Alert.merchant_id == merchant_id).limit(5)
        )
        for a in alerts_result.scalars().all():
            nodes.append({
                "id": str(a.id),
                "type": "alert",
                "label": f"Alert: {a.alert_type}",
                "severity": a.severity,
            })
            edges.append({"from": merchant_id, "to": str(a.id), "relationship": "has_alert"})

        return {"nodes": nodes, "edges": edges}
