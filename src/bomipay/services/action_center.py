import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.alert import Alert, AlertStatus, AlertType
from ..models.incident import Incident, IncidentStatus
from ..models.reconciliation import ReconciliationResult, ReconciliationMatchStatus
from ..models.bank_statement import BankStatementImport, BankStatementImportStatus
from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus

logger = logging.getLogger("bomipay")


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
            actions.append({
                "action_type": "investigate_failed_payment",
                "priority": 1,
                "title": f"Investigate {failed_count} failed payment(s)",
                "description": "Review failed transactions and identify root cause",
                "entity_type": "transaction",
                "count": failed_count,
            })

        # Pending imports
        pending_imports_result = await db.execute(
            select(func.count(BankStatementImport.id)).where(
                BankStatementImport.merchant_id == merchant_id,
                BankStatementImport.status == BankStatementImportStatus.uploaded.value,
            )
        )
        pending_imports = pending_imports_result.scalar() or 0
        if pending_imports > 0:
            actions.append({
                "action_type": "process_bank_statement",
                "priority": 2,
                "title": f"Process {pending_imports} pending bank statement import(s)",
                "description": "Upload or process pending bank statement files",
                "entity_type": "bank_statement_import",
                "count": pending_imports,
            })
        else:
            actions.append({
                "action_type": "upload_bank_statement",
                "priority": 5,
                "title": "Upload bank statement",
                "description": "Upload your latest bank statement for reconciliation",
                "entity_type": "bank_statement_import",
                "count": 0,
            })

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
            actions.append({
                "action_type": "resolve_unmatched_settlement",
                "priority": 2,
                "title": f"Resolve {mismatch_count} unmatched settlement(s)",
                "description": "Review reconciliation results with unmatched or weak matches",
                "entity_type": "reconciliation_result",
                "count": mismatch_count,
            })

        # Open incidents
        incident_result = await db.execute(
            select(Incident).where(
                Incident.merchant_id == merchant_id,
                Incident.status == IncidentStatus.open.value,
            ).order_by(Incident.severity.desc()).limit(3)
        )
        for incident in incident_result.scalars().all():
            actions.append({
                "action_type": "acknowledge_incident",
                "priority": 1 if incident.severity in ("critical", "high") else 3,
                "title": f"Acknowledge incident: {incident.title}",
                "description": f"Severity: {incident.severity}. Needs acknowledgement.",
                "entity_type": "incident",
                "entity_id": str(incident.id),
                "count": 1,
            })

        # Failed sync jobs
        sync_result = await db.execute(
            select(func.count(ProviderSyncJob.id)).where(
                ProviderSyncJob.merchant_id == merchant_id,
                ProviderSyncJob.status == ProviderSyncStatus.failed.value,
            )
        )
        failed_syncs = sync_result.scalar() or 0
        if failed_syncs > 0:
            actions.append({
                "action_type": "check_provider_sync_failure",
                "priority": 2,
                "title": f"Investigate {failed_syncs} failed provider sync(s)",
                "description": "Provider sync jobs failed; manual review needed",
                "entity_type": "provider_sync_job",
                "count": failed_syncs,
            })

        actions.sort(key=lambda x: x["priority"])
        return actions
