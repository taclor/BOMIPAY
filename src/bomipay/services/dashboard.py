import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.alert import Alert, AlertStatus
from ..models.incident import Incident, IncidentStatus
from ..models.reconciliation import Settlement, ReconciliationResult, ReconciliationMatchStatus
from ..models.provider_account import ProviderAccount
from ..models.bank_statement import BankStatementImport

logger = logging.getLogger("bomipay")


class DashboardService:
    @staticmethod
    async def get_mission_control(db: AsyncSession, merchant_id: str) -> dict:
        # Payment success rate
        total_result = await db.execute(
            select(func.count(Transaction.id)).where(Transaction.merchant_id == merchant_id)
        )
        total_txns = total_result.scalar() or 0

        success_result = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.success.value, TransactionStatus.settled.value]),
            )
        )
        success_txns = success_result.scalar() or 0

        failed_result = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
            )
        )
        failed_count = failed_result.scalar() or 0

        success_rate = round((success_txns / total_txns * 100) if total_txns > 0 else 0.0, 2)

        # Money at risk (failed + pending sum)
        risk_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.failed.value, TransactionStatus.pending.value]),
            )
        )
        money_at_risk = risk_result.scalar() or 0

        # Pending settlements
        pending_settlements_result = await db.execute(
            select(func.count(Settlement.id)).where(Settlement.merchant_id == merchant_id)
        )
        pending_settlements = pending_settlements_result.scalar() or 0

        # Open incidents
        open_incidents_result = await db.execute(
            select(func.count(Incident.id)).where(
                Incident.merchant_id == merchant_id,
                Incident.status.in_([IncidentStatus.open.value, IncidentStatus.acknowledged.value]),
            )
        )
        open_incidents = open_incidents_result.scalar() or 0

        # Provider health summary
        providers_result = await db.execute(
            select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id)
        )
        providers = list(providers_result.scalars().all())
        provider_health = [
            {"provider": p.provider_name, "status": p.status} for p in providers
        ]

        # Reconciliation status
        recon_mismatches_result = await db.execute(
            select(func.count(ReconciliationResult.id)).where(
                ReconciliationResult.match_status.in_([
                    ReconciliationMatchStatus.unmatched.value,
                    ReconciliationMatchStatus.weak.value,
                ])
            )
        )
        recon_mismatches = recon_mismatches_result.scalar() or 0

        # Open alerts
        open_alerts_result = await db.execute(
            select(func.count(Alert.id)).where(
                Alert.merchant_id == merchant_id,
                Alert.status == AlertStatus.open.value,
            )
        )
        open_alerts = open_alerts_result.scalar() or 0

        ai_insight = (
            f"You have {open_incidents} open incident(s) and {failed_count} failed transaction(s). "
            f"Payment success rate is {success_rate}%."
        )

        return {
            "payment_success_rate": success_rate,
            "failed_transaction_count": failed_count,
            "money_at_risk_minor": money_at_risk,
            "pending_settlements_count": pending_settlements,
            "open_incidents_count": open_incidents,
            "open_alerts": open_alerts,
            "provider_health_summary": provider_health,
            "reconciliation_status": {"mismatches": recon_mismatches},
            "ai_insight_summary": ai_insight,
        }
