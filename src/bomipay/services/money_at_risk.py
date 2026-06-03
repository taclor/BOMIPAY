import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.reconciliation import ReconciliationResult, ReconciliationMatchStatus, Settlement
from ..models.alert import Alert, AlertStatus
from ..models.incident import Incident, IncidentStatus

logger = logging.getLogger("bomipay")


class MoneyAtRiskService:
    @staticmethod
    async def calculate(
        db: AsyncSession,
        merchant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        def base_txn_stmt():
            stmt = select(Transaction).where(Transaction.merchant_id == merchant_id)
            if date_from:
                stmt = stmt.where(Transaction.created_at >= date_from)
            if date_to:
                stmt = stmt.where(Transaction.created_at <= date_to)
            return stmt

        # Failed payments
        failed_result = await db.execute(
            base_txn_stmt().where(Transaction.status == TransactionStatus.failed.value)
        )
        failed_txns = list(failed_result.scalars().all())
        failed_amount = sum(t.amount for t in failed_txns)

        # Hanging payments (pending older than cutoff — all pending treated as hanging)
        hanging_result = await db.execute(
            base_txn_stmt().where(Transaction.status == TransactionStatus.pending.value)
        )
        hanging_txns = list(hanging_result.scalars().all())
        hanging_amount = sum(t.amount for t in hanging_txns)

        # Unsettled successful payments
        unsettled_result = await db.execute(
            base_txn_stmt().where(Transaction.status == TransactionStatus.success.value)
        )
        unsettled_txns = list(unsettled_result.scalars().all())
        unsettled_amount = sum(t.amount for t in unsettled_txns)

        # Settlement mismatches from reconciliation
        mismatch_stmt = (
            select(ReconciliationResult)
            .where(
                ReconciliationResult.match_status.in_([
                    ReconciliationMatchStatus.unmatched.value,
                    ReconciliationMatchStatus.weak.value,
                    ReconciliationMatchStatus.ambiguous.value,
                ])
            )
        )
        mismatch_result = await db.execute(mismatch_stmt)
        mismatch_count = len(list(mismatch_result.scalars().all()))
        settlement_mismatch_amount = 0

        # Duplicate risk
        duplicate_stmt = select(ReconciliationResult).where(
            ReconciliationResult.match_status == ReconciliationMatchStatus.duplicate.value
        )
        dup_result = await db.execute(duplicate_stmt)
        dup_count = len(list(dup_result.scalars().all()))
        duplicate_amount = 0

        # Unresolved disputes (approximated from open alerts)
        dispute_alerts = await db.execute(
            select(Alert).where(
                Alert.merchant_id == merchant_id,
                Alert.alert_type == "reconciliation_mismatch",
                Alert.status == AlertStatus.open.value,
            )
        )
        dispute_list = list(dispute_alerts.scalars().all())
        dispute_amount = 0

        total = failed_amount + hanging_amount + settlement_mismatch_amount + duplicate_amount + dispute_amount

        # Top providers by risk
        provider_risk: dict[str, int] = {}
        for t in failed_txns + hanging_txns:
            provider_risk[t.provider_name] = provider_risk.get(t.provider_name, 0) + t.amount
        top_providers = sorted(
            [{"provider": p, "amount_minor": a} for p, a in provider_risk.items()],
            key=lambda x: x["amount_minor"],
            reverse=True,
        )[:5]

        # Top open incidents
        incidents_result = await db.execute(
            select(Incident)
            .where(
                Incident.merchant_id == merchant_id,
                Incident.status.in_([IncidentStatus.open.value, IncidentStatus.acknowledged.value]),
            )
            .order_by(Incident.affected_amount_minor.desc())
            .limit(5)
        )
        top_incidents = [
            {"id": str(i.id), "title": i.title, "severity": i.severity, "amount_minor": i.affected_amount_minor}
            for i in incidents_result.scalars().all()
        ]

        recommended_actions = MoneyAtRiskService._recommended_actions(
            failed_amount, hanging_amount, settlement_mismatch_amount, mismatch_count, dup_count
        )

        return {
            "total_money_at_risk_minor": total,
            "failed_payments_amount_minor": failed_amount,
            "hanging_payments_amount_minor": hanging_amount,
            "unsettled_successful_payments_amount_minor": unsettled_amount,
            "settlement_mismatch_amount_minor": settlement_mismatch_amount,
            "duplicate_payment_risk_amount_minor": duplicate_amount,
            "unresolved_dispute_amount_minor": dispute_amount,
            "affected_transaction_count": len(failed_txns) + len(hanging_txns),
            "top_providers_by_risk": top_providers,
            "top_incidents": top_incidents,
            "recommended_actions": recommended_actions,
        }

    @staticmethod
    def _recommended_actions(
        failed: int,
        hanging: int,
        mismatch: int,
        mismatch_count: int,
        dup_count: int,
    ) -> list[str]:
        actions = []
        if failed > 0:
            actions.append("Investigate failed transactions and contact affected customers")
        if hanging > 0:
            actions.append("Review pending transactions; initiate status sync from providers")
        if mismatch > 0 or mismatch_count > 0:
            actions.append("Run reconciliation to identify and resolve settlement mismatches")
        if dup_count > 0:
            actions.append("Review duplicate payment flags and initiate refunds where needed")
        if not actions:
            actions.append("No immediate actions required")
        return actions
