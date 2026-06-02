import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent
from ..models.reconciliation import ReconciliationResult, Settlement
from ..models.incident import Incident
from ..models.alert import Alert
from ..models.bank_statement import BankStatementEntry

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

        return {"nodes": nodes, "edges": edges}
