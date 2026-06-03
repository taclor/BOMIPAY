import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from decimal import Decimal

from sqlalchemy import and_, func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction, TransactionStatus
from ..models.alert import Alert, AlertStatus
from ..models.incident import Incident, IncidentStatus
from ..models.reconciliation import Settlement, ReconciliationResult, ReconciliationMatchStatus, ReconciliationRun
from ..models.provider_account import ProviderAccount
from ..models.provider_sync_job import ProviderSyncJob
from ..models.dashboard import DashboardSnapshot

logger = logging.getLogger("bomipay")


class DashboardService:
    # Cache durations in seconds
    CACHE_REALTIME = 60  # 1 minute
    CACHE_METRICS = 900  # 15 minutes
    CACHE_PROVIDER_HEALTH = 300  # 5 minutes

    @staticmethod
    async def get_realtime_dashboard(db: AsyncSession, merchant_id: str) -> dict:
        """Get complete real-time dashboard aggregating all metrics."""
        now = datetime.now(timezone.utc)
        
        # Aggregate all metrics
        metrics = await DashboardService._aggregate_core_metrics(db, merchant_id)
        performance = await DashboardService._calculate_performance_metrics(db, merchant_id)
        provider_health = await DashboardService._get_provider_health(db, merchant_id)
        operational_status = await DashboardService._get_operational_status(
            db, merchant_id, metrics, performance
        )
        recent_activities = await DashboardService._get_recent_activities(db, merchant_id, limit=20)
        anomalies = await DashboardService._detect_anomalies(db, merchant_id, metrics, performance)
        open_alerts = await DashboardService._get_open_alerts(db, merchant_id, limit=10)
        
        return {
            "snapshot_time": now,
            "total_transactions_processed": metrics["total_transactions"],
            "total_amount_processed": float(metrics["total_amount"]),
            "success_rate": metrics["success_rate"],
            "avg_settlement_time_hours": metrics["avg_settlement_time"],
            "failed_transaction_count": metrics["failed_count"],
            "pending_settlements_count": metrics["pending_settlements"],
            "reconciliation_mismatches_count": metrics["recon_mismatches"],
            "incident_count_open": metrics["open_incidents"],
            "money_at_risk_amount": float(metrics["money_at_risk"]),
            "operational_status": operational_status["status"],
            "system_health_score": operational_status["health_score"],
            "provider_statuses": provider_health,
            "performance_metrics": performance,
            "recent_activities": recent_activities,
            "detected_anomalies": anomalies,
            "open_alerts": open_alerts,
        }

    @staticmethod
    async def _aggregate_core_metrics(db: AsyncSession, merchant_id: str) -> dict:
        """Calculate core transaction and settlement metrics."""
        # Total transactions and success rate
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

        pending_result = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.pending.value,
            )
        )
        pending_count = pending_result.scalar() or 0

        success_rate = round((success_txns / total_txns * 100) if total_txns > 0 else 0.0, 2)

        # Total amount processed
        amount_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.success.value, TransactionStatus.settled.value]),
            )
        )
        total_amount = Decimal(str(amount_result.scalar() or 0))

        # Average settlement time (works on both PostgreSQL and SQLite)
        # Use initiated_at instead of created_at since created_at is auto-set by the database
        settled_txns_result = await db.execute(
            select(Transaction.id, Transaction.settled_at, Transaction.initiated_at).where(
                Transaction.merchant_id == merchant_id,
                Transaction.settled_at.isnot(None),
                Transaction.initiated_at.isnot(None),
            )
        )
        settled_rows = settled_txns_result.fetchall()
        if settled_rows:
            settlement_times = []
            for row in settled_rows:
                settled_at = row[1]
                initiated_at = row[2]
                if settled_at and initiated_at:
                    delta = settled_at - initiated_at
                    hours = delta.total_seconds() / 3600
                    # Only include positive settlement times
                    if hours >= 0:
                        settlement_times.append(hours)
            avg_settlement_hours = sum(settlement_times) / len(settlement_times) if settlement_times else 0
        else:
            avg_settlement_hours = 0

        # Money at risk (failed + pending)
        risk_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.failed.value, TransactionStatus.pending.value]),
            )
        )
        money_at_risk = Decimal(str(risk_result.scalar() or 0))

        # Pending settlements count
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

        # Reconciliation mismatches
        recon_mismatches_result = await db.execute(
            select(func.count(ReconciliationResult.id)).where(
                ReconciliationResult.match_status.in_([
                    ReconciliationMatchStatus.unmatched.value,
                    ReconciliationMatchStatus.weak.value,
                ])
            ).select_from(
                ReconciliationResult
            ).join(
                ReconciliationRun,
                ReconciliationResult.run_id == ReconciliationRun.id
            ).where(
                ReconciliationRun.merchant_id == merchant_id
            )
        )
        recon_mismatches = recon_mismatches_result.scalar() or 0

        return {
            "total_transactions": total_txns,
            "total_amount": total_amount,
            "success_rate": success_rate,
            "success_count": success_txns,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "avg_settlement_time": avg_settlement_hours,
            "money_at_risk": money_at_risk,
            "pending_settlements": pending_settlements,
            "open_incidents": open_incidents,
            "recon_mismatches": recon_mismatches,
        }

    @staticmethod
    async def _calculate_performance_metrics(db: AsyncSession, merchant_id: str) -> dict:
        """Calculate key performance indicators."""
        metrics = await DashboardService._aggregate_core_metrics(db, merchant_id)
        
        # Determine top failure reason by querying failed transactions
        top_failure = await db.execute(
            select(Transaction.status_reason, func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
                Transaction.status_reason.isnot(None),
            ).group_by(Transaction.status_reason).order_by(desc(func.count(Transaction.id))).limit(1)
        )
        top_failure_result = top_failure.first()
        top_failure_reason = top_failure_result[0] if top_failure_result else None

        # Provider error rates
        provider_result = await db.execute(
            select(Transaction.provider_name, func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
            ).group_by(Transaction.provider_name).order_by(desc(func.count(Transaction.id))).limit(1)
        )
        provider_error_result = provider_result.first()
        top_error_provider = provider_error_result[0] if provider_error_result else None

        # Provider health scores
        provider_health = await DashboardService._get_provider_health(db, merchant_id)
        provider_health_scores = {p["provider_name"]: p["health_score"] for p in provider_health}

        return {
            "payment_success_rate": metrics["success_rate"],
            "average_settlement_time_hours": metrics["avg_settlement_time"],
            "failed_transaction_count": metrics["failed_count"],
            "pending_settlement_count": metrics["pending_settlements"],
            "reconciliation_mismatch_count": metrics["recon_mismatches"],
            "provider_health_scores": provider_health_scores,
            "top_failure_reason": top_failure_reason,
            "top_error_provider": top_error_provider,
        }

    @staticmethod
    async def _get_provider_health(db: AsyncSession, merchant_id: str) -> List[dict]:
        """Calculate health scores for all providers."""
        # Get all provider accounts
        providers_result = await db.execute(
            select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id)
        )
        providers = list(providers_result.scalars().all())
        
        provider_health = []
        for provider in providers:
            # Calculate provider-specific metrics
            total = await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider.provider_name,
                )
            )
            total_count = total.scalar() or 1

            success = await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider.provider_name,
                    Transaction.status.in_([TransactionStatus.success.value, TransactionStatus.settled.value]),
                )
            )
            success_count = success.scalar() or 0

            failed = await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider.provider_name,
                    Transaction.status == TransactionStatus.failed.value,
                )
            )
            failed_count = failed.scalar() or 0

            sync_success_rate = round((success_count / total_count * 100) if total_count > 0 else 0, 2)
            error_rate = round((failed_count / total_count * 100) if total_count > 0 else 0, 2)

            # Get recent sync jobs for uptime (filter by provider account)
            syncs = await db.execute(
                select(ProviderSyncJob).where(
                    ProviderSyncJob.merchant_id == merchant_id,
                    ProviderSyncJob.provider_account_id == provider.id,
                ).order_by(desc(ProviderSyncJob.created_at)).limit(10)
            )
            sync_jobs = list(syncs.scalars().all())
            
            if sync_jobs:
                successful_syncs = sum(1 for job in sync_jobs if job.status == "completed")
                uptime_percent = round((successful_syncs / len(sync_jobs) * 100), 2)
            else:
                uptime_percent = 0.0

            # Calculate health score (0-100)
            # Weight: sync_success_rate (40%), uptime (30%), error_rate inverse (30%)
            health_score = (
                sync_success_rate * 0.4 +
                uptime_percent * 0.3 +
                (100 - error_rate) * 0.3
            )

            provider_health.append({
                "provider_name": provider.provider_name,
                "status": provider.status,
                "health_score": round(health_score, 2),
                "uptime_percent": uptime_percent,
                "sync_success_rate": sync_success_rate,
                "error_rate": error_rate,
                "last_sync_at": sync_jobs[0].created_at if sync_jobs else None,
            })

        return provider_health

    @staticmethod
    async def _get_operational_status(db: AsyncSession, merchant_id: str, metrics: dict, performance: dict) -> dict:
        """Determine overall operational status and health score."""
        success_rate = metrics["success_rate"]
        failed_count = metrics["failed_count"]
        open_incidents = metrics["open_incidents"]
        
        # Determine status based on key metrics
        if success_rate < 70 or failed_count > 100 or open_incidents > 5:
            status = "critical"
            health_score = min(success_rate, 40)
        elif success_rate < 85 or failed_count > 50 or open_incidents > 2:
            status = "degraded"
            health_score = min(success_rate, 70)
        else:
            status = "healthy"
            health_score = success_rate

        key_issues = []
        if success_rate < 90:
            key_issues.append(f"Low success rate: {success_rate}%")
        if failed_count > 10:
            key_issues.append(f"High failed transactions: {failed_count}")
        if open_incidents > 0:
            key_issues.append(f"Open incidents: {open_incidents}")
        if performance["top_error_provider"]:
            key_issues.append(f"Issues with provider: {performance['top_error_provider']}")

        return {
            "status": status,
            "health_score": round(health_score, 2),
            "key_issues": key_issues,
        }

    @staticmethod
    async def _get_recent_activities(db: AsyncSession, merchant_id: str, limit: int = 20) -> List[dict]:
        """Get recent activities: transactions, incidents, alerts, settlements."""
        activities = []

        # Recent failed transactions
        failed_txns = await db.execute(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
            ).order_by(desc(Transaction.created_at)).limit(5)
        )
        for txn in failed_txns.scalars().all():
            activities.append({
                "id": str(txn.id),
                "activity_type": "transaction",
                "description": f"Failed transaction: {txn.provider_name} - {txn.provider_transaction_id}",
                "severity": "high",
                "timestamp": txn.created_at,
                "metadata": {"amount": float(txn.amount), "status": txn.status},
            })

        # Recent incidents
        recent_incidents = await db.execute(
            select(Incident).where(
                Incident.merchant_id == merchant_id,
            ).order_by(desc(Incident.created_at)).limit(5)
        )
        for incident in recent_incidents.scalars().all():
            activities.append({
                "id": str(incident.id),
                "activity_type": "incident",
                "description": incident.title or "Incident occurred",
                "severity": incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
                "timestamp": incident.created_at,
                "metadata": {"status": incident.status},
            })

        # Recent alerts
        recent_alerts = await db.execute(
            select(Alert).where(
                Alert.merchant_id == merchant_id,
            ).order_by(desc(Alert.created_at)).limit(5)
        )
        for alert in recent_alerts.scalars().all():
            activities.append({
                "id": str(alert.id),
                "activity_type": "alert",
                "description": alert.description or "Alert triggered",
                "severity": alert.severity if isinstance(alert.severity, str) else alert.severity.value,
                "timestamp": alert.created_at,
                "metadata": {"status": alert.status},
            })

        # Sort by timestamp and limit
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]

    @staticmethod
    async def _detect_anomalies(db: AsyncSession, merchant_id: str, metrics: dict, performance: dict) -> List[dict]:
        """Detect anomalies in metrics and transaction patterns."""
        anomalies = []
        now = datetime.now(timezone.utc)

        # Check for outlier transactions (> 95th percentile)
        # SQLite-compatible percentile calculation
        all_amounts = await db.execute(
            select(Transaction.amount).where(
                Transaction.merchant_id == merchant_id,
                Transaction.amount > 0,
            ).order_by(Transaction.amount)
        )
        amounts = [row[0] for row in all_amounts.fetchall()]
        
        p95_amount = None
        if amounts:
            p95_index = int(len(amounts) * 0.95)
            p95_amount = amounts[p95_index] if p95_index < len(amounts) else amounts[-1]
        
        if p95_amount:
            large_txns = await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.amount > p95_amount,
                    Transaction.created_at > now - timedelta(hours=1),
                )
            )
            large_count = large_txns.scalar() or 0
            if large_count > 0:
                anomalies.append({
                    "anomaly_type": "outlier_transaction",
                    "severity": "medium",
                    "description": f"{large_count} unusually large transaction(s) detected",
                    "value": float(p95_amount),
                    "threshold": float(p95_amount),
                    "detected_at": now,
                })

        # Check for success rate drop (> 10% from baseline)
        # Simple baseline: if current < 85%, it's a concern
        if metrics["success_rate"] < 85:
            anomalies.append({
                "anomaly_type": "success_rate_drop",
                "severity": "high",
                "description": f"Success rate dropped to {metrics['success_rate']}%",
                "value": metrics["success_rate"],
                "threshold": 85.0,
                "detected_at": now,
            })

        # Check for incident spike
        hour_ago = now - timedelta(hours=1)
        recent_incidents = await db.execute(
            select(func.count(Incident.id)).where(
                Incident.merchant_id == merchant_id,
                Incident.created_at > hour_ago,
            )
        )
        recent_incident_count = recent_incidents.scalar() or 0
        if recent_incident_count > 3:
            anomalies.append({
                "anomaly_type": "incident_spike",
                "severity": "critical",
                "description": f"{recent_incident_count} incidents in the last hour",
                "value": float(recent_incident_count),
                "threshold": 3.0,
                "detected_at": now,
            })

        # Check for settlement delay
        if metrics["avg_settlement_time"] > 24:  # More than 24 hours
            anomalies.append({
                "anomaly_type": "settlement_delay",
                "severity": "medium",
                "description": f"Average settlement time: {metrics['avg_settlement_time']:.2f} hours",
                "value": metrics["avg_settlement_time"],
                "threshold": 24.0,
                "detected_at": now,
            })

        return anomalies

    @staticmethod
    async def _get_open_alerts(db: AsyncSession, merchant_id: str, limit: int = 10) -> List[dict]:
        """Get open alerts for the merchant."""
        alerts = await db.execute(
            select(Alert).where(
                Alert.merchant_id == merchant_id,
                Alert.status == AlertStatus.open.value,
            ).order_by(desc(Alert.created_at)).limit(limit)
        )
        
        return [
            {
                "id": str(alert.id),
                "alert_type": alert.alert_type if hasattr(alert, 'alert_type') else "unknown",
                "severity": alert.severity if isinstance(alert.severity, str) else alert.severity.value,
                "message": alert.description,
                "created_at": alert.created_at,
                "status": alert.status,
            }
            for alert in alerts.scalars().all()
        ]

    @staticmethod
    async def get_metrics_summary(db: AsyncSession, merchant_id: str, period: str = "today") -> dict:
        """Get metrics for a specific time period (today/week/month/year)."""
        now = datetime.now(timezone.utc)
        
        # Calculate period boundaries
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now - timedelta(days=1)

        # Get transactions in period
        total = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.created_at >= start_date,
            )
        )
        total_count = total.scalar() or 0

        success = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.success.value, TransactionStatus.settled.value]),
                Transaction.created_at >= start_date,
            )
        )
        success_count = success.scalar() or 0

        failed = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
                Transaction.created_at >= start_date,
            )
        )
        failed_count = failed.scalar() or 0

        pending = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.pending.value,
                Transaction.created_at >= start_date,
            )
        )
        pending_count = pending.scalar() or 0

        # Total amount
        amount = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([TransactionStatus.success.value, TransactionStatus.settled.value]),
                Transaction.created_at >= start_date,
            )
        )
        total_amount = float(amount.scalar() or 0)

        # Fees
        fees = await db.execute(
            select(func.coalesce(func.sum(Transaction.fee_amount), 0)).where(
                Transaction.merchant_id == merchant_id,
                Transaction.fee_amount.isnot(None),
                Transaction.created_at >= start_date,
            )
        )
        total_fees = float(fees.scalar() or 0)

        # Settlement time
        settlement = await db.execute(
            select(
                func.avg(
                    func.extract("epoch", Transaction.settled_at - Transaction.created_at) / 3600
                )
            ).where(
                Transaction.merchant_id == merchant_id,
                Transaction.settled_at.isnot(None),
                Transaction.created_at >= start_date,
            )
        )
        avg_settlement = float(settlement.scalar() or 0)

        success_rate = round((success_count / total_count * 100) if total_count > 0 else 0, 2)

        return {
            "period_type": period,
            "total_transactions": total_count,
            "total_amount_processed": total_amount,
            "success_rate": success_rate,
            "failed_transactions": failed_count,
            "pending_transactions": pending_count,
            "average_settlement_time_hours": avg_settlement,
            "total_fees_collected": total_fees,
        }

    @staticmethod
    async def get_top_transactions(db: AsyncSession, merchant_id: str, limit: int = 10) -> List[dict]:
        """Get largest recent transactions."""
        txns = await db.execute(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
            ).order_by(desc(Transaction.amount)).limit(limit)
        )
        
        return [
            {
                "id": str(t.id),
                "provider": t.provider_name,
                "amount": float(t.amount),
                "status": t.status,
                "created_at": t.created_at,
            }
            for t in txns.scalars().all()
        ]

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
