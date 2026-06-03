import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.alert import Alert, AlertStatus, AlertType
from ..models.incident import Incident, IncidentStatus
from ..models.reconciliation import ReconciliationResult, ReconciliationMatchStatus
from ..models.bank_statement import BankStatementImport, BankStatementImportStatus
from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus
from ..models.bank_account import BankAccount, BankAccountVerificationStatus
from ..models.data_source import DataSource, DataSourceStatus

logger = logging.getLogger("bomipay")

_ACTION_KEYS = ("action_type", "priority", "title", "description", "entity_type", "entity_id", "count", "cta_url")


def _normalize(action: dict) -> dict:
    """Ensure every action dict has the full canonical key set."""
    return {
        "action_type": action.get("action_type"),
        "priority": action.get("priority", 5),
        "title": action.get("title", ""),
        "description": action.get("description", ""),
        "entity_type": action.get("entity_type", ""),
        "entity_id": action.get("entity_id"),
        "count": action.get("count", 0),
        "cta_url": action.get("cta_url"),
    }


class ActionCenterService:
    @staticmethod
    async def get_actions(db: AsyncSession, merchant_id: str) -> list[dict]:
        actions: list[dict] = []

        # Failed transactions
        failed_result = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
            )
        )
        failed_count = failed_result.scalar() or 0
        if failed_count > 0:
            actions.append(_normalize({
                "action_type": "investigate_failed_payment",
                "priority": 1,
                "title": f"Investigate {failed_count} failed payment(s)",
                "description": "Review failed transactions and identify root cause",
                "entity_type": "transaction",
                "count": failed_count,
                "cta_url": f"/merchants/{merchant_id}/transactions?status=failed",
            }))

        # Pending imports
        pending_imports_result = await db.execute(
            select(func.count(BankStatementImport.id)).where(
                BankStatementImport.merchant_id == merchant_id,
                BankStatementImport.status == BankStatementImportStatus.uploaded.value,
            )
        )
        pending_imports = pending_imports_result.scalar() or 0
        if pending_imports > 0:
            actions.append(_normalize({
                "action_type": "process_bank_statement",
                "priority": 2,
                "title": f"Process {pending_imports} pending bank statement import(s)",
                "description": "Upload or process pending bank statement files",
                "entity_type": "bank_statement_import",
                "count": pending_imports,
                "cta_url": f"/merchants/{merchant_id}/bank-statements",
            }))
        else:
            actions.append(_normalize({
                "action_type": "upload_bank_statement",
                "priority": 5,
                "title": "Upload bank statement",
                "description": "Upload your latest bank statement for reconciliation",
                "entity_type": "bank_statement_import",
                "count": 0,
                "cta_url": f"/merchants/{merchant_id}/bank-statements/upload",
            }))

        # Reconciliation mismatches
        mismatch_result = await db.execute(
            select(func.count(ReconciliationResult.id)).where(
                ReconciliationResult.match_status.in_([
                    ReconciliationMatchStatus.unmatched.value,
                    ReconciliationMatchStatus.weak.value,
                ])
            )
        )
        mismatch_count = mismatch_result.scalar() or 0
        if mismatch_count > 0:
            actions.append(_normalize({
                "action_type": "resolve_unmatched_settlement",
                "priority": 2,
                "title": f"Resolve {mismatch_count} unmatched settlement(s)",
                "description": "Review reconciliation results with unmatched or weak matches",
                "entity_type": "reconciliation_result",
                "count": mismatch_count,
                "cta_url": f"/merchants/{merchant_id}/reconciliation",
            }))

        # Open incidents
        incident_result = await db.execute(
            select(Incident).where(
                Incident.merchant_id == merchant_id,
                Incident.status == IncidentStatus.open.value,
            ).order_by(Incident.severity.desc()).limit(3)
        )
        for incident in incident_result.scalars().all():
            actions.append(_normalize({
                "action_type": "acknowledge_incident",
                "priority": 1 if incident.severity in ("critical", "high") else 3,
                "title": f"Acknowledge incident: {incident.title}",
                "description": f"Severity: {incident.severity}. Needs acknowledgement.",
                "entity_type": "incident",
                "entity_id": str(incident.id),
                "count": 1,
                "cta_url": f"/merchants/{merchant_id}/incidents/{incident.id}",
            }))

        # Transactions needing dispute escalation (unmatched reconciliation older than 3 days)
        dispute_cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        dispute_candidate_result = await db.execute(
            select(func.count(ReconciliationResult.id)).where(
                ReconciliationResult.match_status == ReconciliationMatchStatus.unmatched.value,
                ReconciliationResult.created_at < dispute_cutoff,
            )
        )
        dispute_candidates = dispute_candidate_result.scalar() or 0
        if dispute_candidates > 0:
            actions.append(_normalize({
                "action_type": "open_dispute",
                "priority": 2,
                "title": f"Open dispute for {dispute_candidates} long-unmatched transaction(s)",
                "description": "These transactions have been unmatched for over 3 days and may require a formal dispute",
                "entity_type": "reconciliation_result",
                "count": dispute_candidates,
                "cta_url": f"/merchants/{merchant_id}/reconciliation?status=unmatched",
            }))

        # Failed sync jobs
        sync_result = await db.execute(
            select(func.count(ProviderSyncJob.id)).where(
                ProviderSyncJob.merchant_id == merchant_id,
                ProviderSyncJob.status == ProviderSyncStatus.failed.value,
            )
        )
        failed_syncs = sync_result.scalar() or 0
        if failed_syncs > 0:
            actions.append(_normalize({
                "action_type": "check_provider_sync_failure",
                "priority": 2,
                "title": f"Investigate {failed_syncs} failed provider sync(s)",
                "description": "Provider sync jobs failed; manual review needed",
                "entity_type": "provider_sync_job",
                "count": failed_syncs,
                "cta_url": f"/merchants/{merchant_id}/provider-syncs",
            }))

        # Unverified bank accounts
        unverified_result = await db.execute(
            select(func.count(BankAccount.id)).where(
                BankAccount.merchant_id == merchant_id,
                BankAccount.verification_status != BankAccountVerificationStatus.verified.value,
            )
        )
        unverified_count = unverified_result.scalar() or 0
        if unverified_count > 0:
            actions.append(_normalize({
                "action_type": "verify_bank_account",
                "priority": 3,
                "title": f"Verify {unverified_count} bank account(s)",
                "description": "Bank accounts pending verification cannot be used for payouts",
                "entity_type": "bank_account",
                "count": unverified_count,
                "cta_url": f"/merchants/{merchant_id}/bank-accounts",
            }))

        # Stale/errored data sources
        stale_result = await db.execute(
            select(func.count(DataSource.id)).where(
                DataSource.merchant_id == merchant_id,
                DataSource.status == DataSourceStatus.error.value,
            )
        )
        stale_count = stale_result.scalar() or 0
        if stale_count > 0:
            actions.append(_normalize({
                "action_type": "reconnect_data_source",
                "priority": 2,
                "title": f"Reconnect {stale_count} data source(s) with errors",
                "description": "Data sources in error state are not syncing; reconnect to resume",
                "entity_type": "data_source",
                "count": stale_count,
                "cta_url": f"/merchants/{merchant_id}/data-sources",
            }))

        # Pending transactions older than 2 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        stale_pending_result = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.pending.value,
                Transaction.created_at < cutoff,
            )
        )
        stale_pending = stale_pending_result.scalar() or 0
        if stale_pending > 0:
            actions.append(_normalize({
                "action_type": "follow_up_pending_payment",
                "priority": 2,
                "title": f"Follow up on {stale_pending} stale pending payment(s)",
                "description": "Transactions have been pending for over 2 hours and may need manual follow-up",
                "entity_type": "transaction",
                "count": stale_pending,
                "cta_url": f"/merchants/{merchant_id}/transactions?status=pending",
            }))

        actions.sort(key=lambda x: x["priority"])
        return actions

    @staticmethod
    async def get_action_stats(db: AsyncSession, merchant_id: str) -> dict:
        actions = await ActionCenterService.get_actions(db, merchant_id)
        by_type = {a["action_type"]: a["count"] for a in actions}
        critical = sum(1 for a in actions if a["priority"] == 1)
        high_priority = sum(1 for a in actions if a["priority"] == 2)
        return {
            "total": len(actions),
            "critical": critical,
            "high_priority": high_priority,
            "by_type": by_type,
        }

    @staticmethod
    async def dismiss_action(db: AsyncSession, merchant_id: str, action_type: str) -> dict:
        # Placeholder — actions are computed dynamically; persistence layer can be added later
        return {"dismissed": True, "action_type": action_type}
