import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent
from ..models.reconciliation import Settlement
from ..models.alert import Alert
from ..models.incident import Incident
from ..models.bank_statement import BankStatementEntry

logger = logging.getLogger("bomipay")


class TimelineService:
    @staticmethod
    async def get_payment_timeline(
        db: AsyncSession,
        merchant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        events: list[dict] = []

        # Transactions
        txn_stmt = select(Transaction).where(Transaction.merchant_id == merchant_id)
        if date_from:
            txn_stmt = txn_stmt.where(Transaction.created_at >= date_from)
        if date_to:
            txn_stmt = txn_stmt.where(Transaction.created_at <= date_to)
        if status:
            txn_stmt = txn_stmt.where(Transaction.status == status)
        if provider:
            txn_stmt = txn_stmt.where(Transaction.provider_name == provider)
        txn_stmt = txn_stmt.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        txn_result = await db.execute(txn_stmt)
        for t in txn_result.scalars().all():
            events.append({
                "event_type": "transaction_created",
                "timestamp": t.created_at.isoformat() if t.created_at else None,
                "entity_type": "transaction",
                "entity_id": str(t.id),
                "summary": f"{t.status} transaction of {t.amount} {t.currency} via {t.provider_name}",
                "provider": t.provider_name,
                "status": t.status,
                "amount_minor": t.amount,
                "currency": t.currency,
            })

        # Settlements
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
                "provider": s.provider_name,
                "amount_minor": s.amount,
                "currency": s.currency,
            })

        # Incidents
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
                "severity": i.severity,
                "status": i.status,
            })

        # Bank statement entries
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
                "credit_amount_minor": e.credit_amount_minor,
                "debit_amount_minor": e.debit_amount_minor,
                "currency": e.currency,
            })

        events.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return events[:limit]
