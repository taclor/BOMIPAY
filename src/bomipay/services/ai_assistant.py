"""
AI Assistant Service — retrieval-grounded intelligence layer.

Rules enforced here:
- All numeric facts come from database queries, never invented.
- AI may not mutate financial state.
- Confidence score is derived from data completeness, not model certainty.
- Cited records carry internal IDs so the frontend can deep-link.
- Suggested actions are presented separately from factual findings.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import timedelta

from ..models.alert import Alert, AlertStatus
from ..models.bank_statement import BankStatementEntry, BankStatementImport
from ..models.data_source import DataSource
from ..models.incident import Incident, IncidentStatus
from ..models.provider_account import ProviderAccount
from ..models.provider_sync_job import ProviderSyncJob
from ..models.reconciliation import ReconciliationResult, Settlement
from ..models.transaction import Transaction, TransactionStatus
from ..models.ai_prompt_version import AIResponseLog
from ..models.ai_token_usage import AITokenUsage
from .ai_safety import AISafetyChecker
from .ai_observability import AITokenCounter, AITokenAnalytics
from .ai_versioning import AIPromptVersionManager

logger = logging.getLogger("bomipay")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cite(record_type: str, record_id, summary: str) -> dict:
    return {"type": record_type, "id": str(record_id), "summary": summary}


def _action(action_type: str, description: str, priority: str = "medium", entity_id: Optional[str] = None) -> dict:
    item = {"action_type": action_type, "description": description, "priority": priority}
    if entity_id:
        item["entity_id"] = entity_id
    return item


def _confidence_score_bps(data_points: int, max_points: int = 6) -> int:
    """Confidence proportional to the number of data sources with non-zero findings."""
    return max(0, min(10000, int(round((data_points / max_points) * 10000))))


# ---------------------------------------------------------------------------
# Context collectors
# ---------------------------------------------------------------------------

async def _collect_failed_transactions(db: AsyncSession, merchant_id: str, limit: int = 10):
    result = await db.execute(
        select(Transaction).where(
            Transaction.merchant_id == merchant_id,
            Transaction.status == TransactionStatus.failed.value,
        ).order_by(Transaction.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _collect_open_incidents(db: AsyncSession, merchant_id: str, limit: int = 10):
    result = await db.execute(
        select(Incident).where(
            Incident.merchant_id == merchant_id,
            Incident.status.in_([
                IncidentStatus.open.value,
                IncidentStatus.acknowledged.value,
                IncidentStatus.investigating.value,
            ]),
        ).order_by(Incident.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _collect_provider_failure_summary(db: AsyncSession, merchant_id: str):
    """Return per-provider counts of failed transactions."""
    result = await db.execute(
        select(Transaction.provider_name, func.count(Transaction.id).label("failures"))
        .where(
            Transaction.merchant_id == merchant_id,
            Transaction.status == TransactionStatus.failed.value,
        )
        .group_by(Transaction.provider_name)
        .order_by(func.count(Transaction.id).desc())
        .limit(5)
    )
    return [{"provider": row.provider_name, "failure_count": row.failures} for row in result.all()]


async def _collect_recon_mismatches(db: AsyncSession, merchant_id: str, limit: int = 10):
    from ..models.reconciliation import ReconciliationRun
    result = await db.execute(
        select(ReconciliationResult)
        .join(ReconciliationRun, ReconciliationResult.run_id == ReconciliationRun.id)
        .where(
            ReconciliationRun.merchant_id == merchant_id,
            ReconciliationResult.match_status.in_(["unmatched", "weak", "ambiguous"]),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def _collect_data_source_health(db: AsyncSession, merchant_id: str):
    result = await db.execute(
        select(DataSource).where(DataSource.merchant_id == merchant_id)
    )
    return list(result.scalars().all())


async def _collect_recent_sync_jobs(db: AsyncSession, merchant_id: str, limit: int = 5):
    result = await db.execute(
        select(ProviderSyncJob).where(
            ProviderSyncJob.merchant_id == merchant_id,
        ).order_by(ProviderSyncJob.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _collect_unmatched_bank_entries(db: AsyncSession, merchant_id: str, limit: int = 5):
    result = await db.execute(
        select(BankStatementEntry).where(
            BankStatementEntry.merchant_id == merchant_id,
        ).order_by(BankStatementEntry.entry_date.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _collect_money_at_risk_totals(db: AsyncSession, merchant_id: str) -> dict:
    failed_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.merchant_id == merchant_id,
            Transaction.status == TransactionStatus.failed.value,
        )
    )
    failed_amount = int(failed_result.scalar() or 0)

    pending_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.merchant_id == merchant_id,
            Transaction.status == TransactionStatus.pending.value,
        )
    )
    pending_amount = int(pending_result.scalar() or 0)

    open_alert_result = await db.execute(
        select(func.count(Alert.id)).where(
            Alert.merchant_id == merchant_id,
            Alert.status == AlertStatus.open.value,
        )
    )
    open_alerts = int(open_alert_result.scalar() or 0)

    return {
        "failed_amount_minor": failed_amount,
        "pending_amount_minor": pending_amount,
        "total_at_risk_minor": failed_amount + pending_amount,
        "open_alerts": open_alerts,
    }


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------

async def _handle_money_at_risk(db: AsyncSession, merchant_id: str) -> dict:
    totals = await _collect_money_at_risk_totals(db, merchant_id)
    incidents = await _collect_open_incidents(db, merchant_id)
    failed_txns = await _collect_failed_transactions(db, merchant_id)
    provider_summary = await _collect_provider_failure_summary(db, merchant_id)

    cited = []
    for inc in incidents:
        cited.append(_cite("incident", inc.id, f"Incident: {inc.title} [{inc.severity}]"))
    for txn in failed_txns[:5]:
        cited.append(_cite("transaction", txn.id, f"Failed transaction {txn.provider_transaction_id} ({txn.currency} {txn.amount})"))

    suggested = []
    if totals["failed_amount_minor"] > 0:
        suggested.append(_action("investigate_failed_payments", f"Investigate {len(failed_txns)} failed transaction(s) totalling {totals['failed_amount_minor']} minor units.", priority="high"))
    if incidents:
        suggested.append(_action("acknowledge_incident", f"Acknowledge {len(incidents)} open incident(s).", priority="high"))
    if totals["open_alerts"] > 0:
        suggested.append(_action("review_alerts", f"Review {totals['open_alerts']} open alert(s).", priority="medium"))

    data_points = sum([
        1 if totals["failed_amount_minor"] > 0 else 0,
        1 if totals["pending_amount_minor"] > 0 else 0,
        1 if incidents else 0,
        1 if provider_summary else 0,
    ])

    worst_provider = provider_summary[0]["provider"] if provider_summary else None
    answer_parts = [f"Total money at risk: {totals['total_at_risk_minor']} minor units."]
    if totals["failed_amount_minor"] > 0:
        answer_parts.append(f"Failed payments: {totals['failed_amount_minor']} minor units across {len(failed_txns)} transaction(s).")
    if totals["pending_amount_minor"] > 0:
        answer_parts.append(f"Pending (potentially stuck): {totals['pending_amount_minor']} minor units.")
    if worst_provider:
        answer_parts.append(f"Highest failure rate: provider '{worst_provider}'.")
    if not cited:
        answer_parts.append("No specific problematic records found at this time.")

    return {
        "answer": " ".join(answer_parts),
        "confidence_score_bps": _confidence_score_bps(data_points),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {**totals, "top_providers_by_failure": provider_summary},
    }


async def _handle_provider_problems(db: AsyncSession, merchant_id: str) -> dict:
    provider_summary = await _collect_provider_failure_summary(db, merchant_id)
    sync_jobs = await _collect_recent_sync_jobs(db, merchant_id)
    incidents = await _collect_open_incidents(db, merchant_id)

    cited = []
    for inc in incidents:
        cited.append(_cite("incident", inc.id, f"Incident: {inc.title} — provider: {inc.provider_name or 'unknown'}"))
    for job in sync_jobs:
        if job.status == "failed":
            cited.append(_cite("provider_sync_job", job.id, f"Failed sync job ({job.sync_type}) for provider account {job.provider_account_id}"))

    suggested = []
    failed_sync_jobs = [j for j in sync_jobs if j.status == "failed"]
    if failed_sync_jobs:
        suggested.append(_action("retry_sync", f"Retry {len(failed_sync_jobs)} failed sync job(s).", priority="high"))
    if provider_summary:
        top = provider_summary[0]
        suggested.append(_action("contact_provider", f"Contact provider '{top['provider']}' — {top['failure_count']} failures recorded.", priority="high"))

    answer_parts = []
    if provider_summary:
        ranks = "; ".join(f"{p['provider']}: {p['failure_count']} failures" for p in provider_summary)
        answer_parts.append(f"Provider failure ranking: {ranks}.")
    else:
        answer_parts.append("No provider failure data found.")
    if failed_sync_jobs:
        answer_parts.append(f"{len(failed_sync_jobs)} recent sync job(s) failed.")

    return {
        "answer": " ".join(answer_parts) if answer_parts else "No provider problems detected.",
        "confidence_score_bps": _confidence_score_bps(len(provider_summary) + len(failed_sync_jobs)),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {"provider_failure_summary": provider_summary},
    }


async def _handle_settlement_mismatch(db: AsyncSession, merchant_id: str) -> dict:
    mismatches = await _collect_recon_mismatches(db, merchant_id)
    bank_entries = await _collect_unmatched_bank_entries(db, merchant_id)

    cited = []
    for mm in mismatches:
        cited.append(_cite("reconciliation_result", mm.id, f"Unmatched reconciliation — status: {mm.match_status}"))
    for entry in bank_entries[:5]:
        cited.append(_cite("bank_statement_entry", entry.id, f"Bank entry {entry.entry_date}: {entry.description} ({entry.credit_amount_minor} credit)"))

    suggested = []
    if mismatches:
        suggested.append(_action("resolve_reconciliation_mismatch", f"Resolve {len(mismatches)} unmatched reconciliation record(s).", priority="high"))
    if not bank_entries:
        suggested.append(_action("upload_bank_statement", "Upload your latest bank statement to enable reconciliation.", priority="medium"))

    answer_parts = [f"{len(mismatches)} reconciliation mismatch(es) found."]
    if bank_entries:
        answer_parts.append(f"{len(bank_entries)} recent bank statement entries available.")
    else:
        answer_parts.append("No bank statement entries found — upload a bank statement for full reconciliation.")

    return {
        "answer": " ".join(answer_parts),
        "confidence_score_bps": _confidence_score_bps(len(mismatches) + (1 if bank_entries else 0)),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {"reconciliation_mismatches": len(mismatches), "bank_entries_available": len(bank_entries)},
    }


async def _handle_what_to_do_today(db: AsyncSession, merchant_id: str) -> dict:
    totals = await _collect_money_at_risk_totals(db, merchant_id)
    incidents = await _collect_open_incidents(db, merchant_id)
    provider_summary = await _collect_provider_failure_summary(db, merchant_id)
    data_sources = await _collect_data_source_health(db, merchant_id)

    cited = []
    for inc in incidents[:3]:
        cited.append(_cite("incident", inc.id, f"{inc.severity.upper()} incident: {inc.title}"))

    suggested = []
    if incidents:
        critical = [i for i in incidents if i.severity in ("critical", "high")]
        if critical:
            suggested.append(_action("acknowledge_incident", f"Acknowledge {len(critical)} critical/high incident(s) immediately.", priority="critical"))
    if totals["failed_amount_minor"] > 0:
        suggested.append(_action("investigate_failed_payments", f"Investigate failed payments: {totals['failed_amount_minor']} minor units at risk.", priority="high"))
    unhealthy_sources = [ds for ds in data_sources if ds.status in ("error", "pending_setup")]
    if unhealthy_sources:
        suggested.append(_action("fix_data_source", f"Fix {len(unhealthy_sources)} data source(s) with errors.", priority="medium"))
    if not suggested:
        suggested.append(_action("review_dashboard", "No urgent actions detected. Review the dashboard for latest insights.", priority="low"))

    answer_parts = ["Priority actions for today:"]
    if incidents:
        answer_parts.append(f"You have {len(incidents)} open incident(s).")
    if totals["failed_amount_minor"] > 0:
        answer_parts.append(f"{totals['failed_amount_minor']} minor units in failed payments need attention.")
    if provider_summary:
        answer_parts.append(f"Top provider by failures: {provider_summary[0]['provider']}.")
    if not incidents and totals["total_at_risk_minor"] == 0:
        answer_parts = ["No urgent actions detected. All systems appear healthy."]

    return {
        "answer": " ".join(answer_parts),
        "confidence_score_bps": _confidence_score_bps(len(incidents) + (1 if totals["total_at_risk_minor"] > 0 else 0)),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {**totals, "open_incidents": len(incidents), "unhealthy_data_sources": len(unhealthy_sources)},
    }


# ---------------------------------------------------------------------------
# New handlers: incident_analysis, trend_analysis, data_health
# ---------------------------------------------------------------------------

async def _handle_incident_analysis(db: AsyncSession, merchant_id: str) -> dict:
    incidents = await _collect_open_incidents(db, merchant_id, limit=50)
    provider_summary = await _collect_provider_failure_summary(db, merchant_id)
    sync_jobs = await _collect_recent_sync_jobs(db, merchant_id, limit=10)

    by_severity: dict = {}
    for inc in incidents:
        by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1

    critical_incidents = [i for i in incidents if i.severity == "critical"]
    high_incidents = [i for i in incidents if i.severity == "high"]
    failed_sync_jobs = [j for j in sync_jobs if j.status == "failed"]

    cited = []
    for inc in incidents:
        cited.append(_cite("incident", inc.id, f"[{inc.severity.upper()}] {inc.title} — status: {inc.status}"))

    suggested = []
    if critical_incidents:
        suggested.append(_action("escalate_incident", f"Escalate {len(critical_incidents)} critical incident(s) immediately.", priority="critical"))
    if high_incidents:
        suggested.append(_action("acknowledge_incident", f"Acknowledge {len(high_incidents)} high-severity incident(s).", priority="high"))
    if failed_sync_jobs:
        suggested.append(_action("investigate_sync_failures", f"Investigate {len(failed_sync_jobs)} failed sync job(s).", priority="medium"))

    top_provider = provider_summary[0]["provider"] if provider_summary else None
    answer_parts = [f"{len(incidents)} open incident(s)."]
    if by_severity.get("critical", 0):
        answer_parts.append(f"{by_severity['critical']} critical.")
    if top_provider:
        answer_parts.append(f"Top affected provider: {top_provider}.")
    if not incidents:
        answer_parts = ["No open incidents found."]

    return {
        "answer": " ".join(answer_parts),
        "confidence_score_bps": _confidence_score_bps(len(incidents) + len(failed_sync_jobs)),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {
            "open_incidents": len(incidents),
            "by_severity": by_severity,
        },
    }


async def _handle_trend_analysis(db: AsyncSession, merchant_id: str) -> dict:
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    total_txn_result = await db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.merchant_id == merchant_id,
            Transaction.created_at >= thirty_days_ago,
        )
    )
    total_transactions = int(total_txn_result.scalar() or 0)

    volume_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.merchant_id == merchant_id,
            Transaction.created_at >= thirty_days_ago,
        )
    )
    total_volume = int(volume_result.scalar() or 0)

    failed_result = await db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.merchant_id == merchant_id,
            Transaction.created_at >= thirty_days_ago,
            Transaction.status == TransactionStatus.failed.value,
        )
    )
    failed_count = int(failed_result.scalar() or 0)

    settled_result = await db.execute(
        select(func.count(Settlement.id), func.coalesce(func.sum(Settlement.amount), 0)).where(
            Settlement.merchant_id == merchant_id,
            Settlement.settled_at >= thirty_days_ago,
        )
    )
    settled_row = settled_result.one()
    settled_count = int(settled_row[0] or 0)
    settlement_total = int(settled_row[1] or 0)

    suggested = []
    if total_transactions > 0 and failed_count / total_transactions > 0.1:
        suggested.append(_action("investigate_failed_payments", f"High failure rate detected: {failed_count}/{total_transactions} transactions failed.", priority="high"))
    if total_volume == 0 and total_transactions > 0:
        suggested.append(_action("check_providers", "Transaction volume is zero — check provider connections.", priority="medium"))

    return {
        "answer": (
            f"Over last 30 days: {total_transactions} transactions totalling {total_volume} minor units. "
            f"{failed_count} failed. {settled_count} settled."
        ),
        "confidence_score_bps": _confidence_score_bps(
            sum([1 if total_transactions > 0 else 0, 1 if total_volume > 0 else 0, 1 if settled_count > 0 else 0])
        ),
        "cited_records": [],
        "suggested_actions": suggested,
        "context_used": {
            "total_transactions": total_transactions,
            "total_volume": total_volume,
            "failed_count": failed_count,
            "settled_count": settled_count,
            "settlement_total": settlement_total,
        },
    }


async def _handle_data_health(db: AsyncSession, merchant_id: str) -> dict:
    data_sources = await _collect_data_source_health(db, merchant_id)
    sync_jobs = await _collect_recent_sync_jobs(db, merchant_id, limit=10)

    provider_accounts_result = await db.execute(
        select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id)
    )
    provider_accounts = list(provider_accounts_result.scalars().all())

    healthy = [ds for ds in data_sources if ds.status == "active"]
    error_sources = [ds for ds in data_sources if ds.status in ("error", "pending_setup")]
    failed_sync_jobs = [j for j in sync_jobs if j.status == "failed"]

    cited = []
    for ds in error_sources:
        cited.append(_cite("data_source", ds.id, f"[{ds.status.upper()}] {ds.display_name} ({ds.source_type})"))
    for job in failed_sync_jobs:
        cited.append(_cite("provider_sync_job", job.id, f"Failed sync job ({job.sync_type})"))

    suggested = []
    reconnect_sources = [ds for ds in error_sources if ds.status == "error"]
    if reconnect_sources:
        suggested.append(_action("reconnect_data_source", f"Reconnect {len(reconnect_sources)} data source(s) with errors.", priority="high"))
    setup_sources = [ds for ds in error_sources if ds.status == "pending_setup"]
    if setup_sources:
        suggested.append(_action("complete_data_source_setup", f"Complete setup for {len(setup_sources)} pending data source(s).", priority="medium"))
    if failed_sync_jobs:
        suggested.append(_action("retry_sync", f"Retry {len(failed_sync_jobs)} failed sync job(s).", priority="medium"))
    if not data_sources:
        suggested.append(_action("add_data_source", "No data sources configured — add a provider connection or bank feed.", priority="high"))

    return {
        "answer": (
            f"{len(data_sources)} data source(s). "
            f"{len(healthy)} healthy, {len(error_sources)} with errors. "
            f"{len(provider_accounts)} provider account(s) connected."
        ),
        "confidence_score_bps": _confidence_score_bps(
            sum([1 if data_sources else 0, 1 if provider_accounts else 0, 1 if not error_sources else 0])
        ),
        "cited_records": cited,
        "suggested_actions": suggested,
        "context_used": {
            "total_data_sources": len(data_sources),
            "healthy": len(healthy),
            "error": len(error_sources),
            "provider_accounts": len(provider_accounts),
            "recent_sync_failures": len(failed_sync_jobs),
        },
    }


# ---------------------------------------------------------------------------
# Query classifier
# ---------------------------------------------------------------------------

_QUERY_KEYWORDS = {
    "money_at_risk": ["money at risk", "stuck", "failed", "delayed", "unresolved money", "how much"],
    "provider_problems": ["provider", "payment gateway", "causing problems", "most problems", "failing provider"],
    "settlement_mismatch": ["settlement", "bank statement", "mismatch", "reconciliation", "not matching"],
    "what_to_do": ["what should", "first today", "priority", "do first", "action", "todo"],
    "incident_analysis": ["incident", "outage", "active incident", "show incidents", "what incidents"],
    "trend_analysis": ["trend", "pattern", "over time", "last week", "last month", "volume", "history"],
    "data_health": ["data source", "sync health", "connection", "integration", "health check", "data feed"],
}

_CATEGORY_DESCRIPTIONS = {
    "money_at_risk": "Analyse failed and pending transactions, open alerts and exposure totals.",
    "provider_problems": "Identify payment providers with high failure rates or sync issues.",
    "settlement_mismatch": "Find reconciliation mismatches between settlements and bank statements.",
    "what_to_do": "Get prioritised action items for the current day.",
    "incident_analysis": "Review open incidents, outages and their severity breakdown.",
    "trend_analysis": "Analyse transaction volumes, failure rates and settlement trends over time.",
    "data_health": "Check the health of data sources, sync jobs and provider connections.",
}


def _classify_query(query: str) -> str:
    lower = query.lower()
    for category, keywords in _QUERY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "general"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class AIAssistantService:
    @staticmethod
    async def query(
        db: AsyncSession,
        merchant_id: str,
        query: str,
        transaction_id: Optional[str] = None,
        settlement_id: Optional[str] = None,
    ) -> dict:
        category = _classify_query(query)
        logger.info(
            "ai_assistant.query",
            extra={"merchant_id": merchant_id, "category": category},
        )

        if category == "money_at_risk":
            result = await _handle_money_at_risk(db, merchant_id)
        elif category == "provider_problems":
            result = await _handle_provider_problems(db, merchant_id)
        elif category == "settlement_mismatch":
            result = await _handle_settlement_mismatch(db, merchant_id)
        elif category == "what_to_do":
            result = await _handle_what_to_do_today(db, merchant_id)
        elif category == "incident_analysis":
            result = await _handle_incident_analysis(db, merchant_id)
        elif category == "trend_analysis":
            result = await _handle_trend_analysis(db, merchant_id)
        elif category == "data_health":
            result = await _handle_data_health(db, merchant_id)
        else:
            # General fallback — return a summary of key health metrics
            totals = await _collect_money_at_risk_totals(db, merchant_id)
            incidents = await _collect_open_incidents(db, merchant_id)
            result = {
                "answer": (
                    f"Here is a summary: {totals['total_at_risk_minor']} minor units at risk, "
                    f"{len(incidents)} open incident(s). Use a more specific query for deeper analysis."
                ),
                "confidence_score_bps": 5000,
                "cited_records": [_cite("incident", i.id, i.title) for i in incidents[:3]],
                "suggested_actions": [
                    _action("review_dashboard", "Check the Mission Control dashboard for a full overview.", priority="low")
                ],
                "context_used": {**totals, "open_incidents": len(incidents)},
            }

        return {
            "query": query,
            "query_category": category,
            "merchant_id": merchant_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    @staticmethod
    def get_categories() -> list:
        return [
            {
                "name": name,
                "keywords": keywords,
                "description": _CATEGORY_DESCRIPTIONS.get(name, ""),
            }
            for name, keywords in _QUERY_KEYWORDS.items()
        ]

    @staticmethod
    async def query_with_safety(
        db: AsyncSession,
        merchant_id: str,
        query: str,
        max_tokens: int = 500,
        transaction_id: Optional[str] = None,
        settlement_id: Optional[str] = None,
    ) -> dict:
        """
        Execute AI query with full safety checks, logging, and observability.

        Flow:
        1. Get retrieval context (from DB)
        2. Check safety flags
        3. Build prompt with version
        4. Call query handler (simulates LLM)
        5. Check for hallucinations
        6. Log response + usage
        7. Return result

        Args:
            db: Database session
            merchant_id: Merchant ID
            query: User query
            max_tokens: Maximum tokens for response
            transaction_id: Optional transaction context
            settlement_id: Optional settlement context

        Returns:
            {
                "response": "...",
                "confidence_score_bps": 8500,
                "sources": ["incident_123", "txn_456", ...],
                "token_usage": {"query": 50, "response": 100},
                "caveats": [str],
                "is_safe": bool,
                "has_hallucinations": bool,
            }
        """
        # Step 1: Get current prompt version
        prompt_version = await AIPromptVersionManager.get_current_version(db)
        logger.info(
            "ai_assistant.query_with_safety.start",
            extra={"merchant_id": merchant_id, "query": query, "version": prompt_version.version}
        )

        # Step 2: Get the query result (using existing logic)
        base_result = await AIAssistantService.query(
            db,
            merchant_id=merchant_id,
            query=query,
            transaction_id=transaction_id,
            settlement_id=settlement_id,
        )

        response_text = base_result.get("answer", "")
        confidence_bps = base_result.get("confidence_score_bps", 5000)
        cited_records = base_result.get("cited_records", [])
        context_used = base_result.get("context_used", {})

        # Prepare context for safety checks
        context_for_safety = {
            **context_used,
            "cited_records": cited_records,
            "data_points": sum([
                1 if v else 0
                for v in context_used.values()
                if v not in (0, None, [], {})
            ]),
        }

        # Step 3: Check for hallucinations
        safety_result = await AISafetyChecker.check_response_safety(
            query=query,
            response=response_text,
            context=context_for_safety,
        )

        has_hallucinations = safety_result.get("hallucinations_check", {}).get("has_hallucinations", False)
        overall_confidence = safety_result.get("overall_confidence", 50)

        # Adjust confidence if safety check detected issues
        if not safety_result.get("safe", False):
            confidence_bps = min(confidence_bps, int(overall_confidence * 100))

        # Step 4: Estimate token usage
        context_summary = f"Data sources: {', '.join(str(k) for k in context_used.keys() if context_used.get(k))}"
        query_tokens = AITokenCounter.estimate_context_tokens({
            "query": query,
            "context": context_summary,
        })
        response_tokens = AITokenCounter.estimate_response_tokens(response_text)

        # Step 5: Log response
        log_record = AIResponseLog(
            merchant_id=merchant_id,
            prompt_version=prompt_version.version,
            model_name=prompt_version.model_name,
            query=query,
            context_sources=context_for_safety,
            response_text=response_text,
            confidence_score=confidence_bps,
            has_hallucinations=1 if has_hallucinations else 0,
            cited_record_ids=cited_records,
            retrieval_query=f"Query for: {query[:100]}",  # Simplified
            response_metadata={
                "query_category": base_result.get("query_category", "general"),
                "safety_check": safety_result,
            },
        )
        db.add(log_record)
        await db.flush()

        # Step 6: Log token usage
        token_usage = await AITokenCounter.log_token_usage(
            db=db,
            merchant_id=merchant_id,
            ai_response_log_id=str(log_record.id),
            query_tokens=query_tokens,
            response_tokens=response_tokens,
            model_name=prompt_version.model_name,
        )

        # Prepare final response
        caveats = []
        if safety_result.get("warnings"):
            caveats.extend(safety_result["warnings"])
        if not safety_result.get("safe", False):
            caveats.append("Response has moderate confidence — verify critical claims before acting")

        # Extract cited IDs
        cited_ids = [rec.get("id") for rec in cited_records]

        logger.info(
            "ai_assistant.query_with_safety.complete",
            extra={
                "merchant_id": merchant_id,
                "confidence_bps": confidence_bps,
                "has_hallucinations": has_hallucinations,
                "total_tokens": token_usage.total_tokens,
                "cost_cents": token_usage.cost_cents,
            }
        )

        return {
            "response": response_text,
            "confidence_score_bps": confidence_bps,
            "sources": cited_ids,
            "token_usage": {
                "query": query_tokens,
                "response": response_tokens,
                "total": token_usage.total_tokens,
                "cost_cents": token_usage.cost_cents,
            },
            "caveats": caveats,
            "is_safe": safety_result.get("safe", False),
            "has_hallucinations": has_hallucinations,
            "response_log_id": str(log_record.id),
        }
