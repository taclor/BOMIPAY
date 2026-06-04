from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.provider_health import HealthStatus, ProviderHealthMetrics
from ..models.reconciliation import Settlement
from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent


class ProviderHealthService:
    @staticmethod
    async def calculate_daily_metrics(
        db: AsyncSession, merchant_id, provider_name: str, metric_date: date
    ) -> ProviderHealthMetrics:
        """Calculate metrics for a specific day."""

        # Query transactions for the day
        day_start = datetime.combine(metric_date, datetime.min.time())
        day_end = datetime.combine(metric_date, datetime.max.time())

        # Transaction metrics
        tx_result = await db.execute(
            select(
                func.count(Transaction.id).label("total"),
                func.sum(
                    case((Transaction.status == TransactionStatus.success.value, 1), else_=0)
                ).label("success_count"),
                func.sum(
                    case((Transaction.status == TransactionStatus.failed.value, 1), else_=0)
                ).label("fail_count"),
            ).where(
                and_(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider_name,
                    Transaction.created_at >= day_start,
                    Transaction.created_at < day_end,
                )
            )
        )

        tx_row = tx_result.first()
        transaction_count = tx_row.total or 0 if tx_row else 0
        transaction_success_count = tx_row.success_count or 0 if tx_row else 0
        transaction_fail_count = tx_row.fail_count or 0 if tx_row else 0
        transaction_avg_latency_ms = 0  # Not tracked in current schema

        # Settlement metrics
        settlement_result = await db.execute(
            select(
                func.count(Settlement.id).label("total"),
                func.avg(func.extract("epoch", Settlement.settled_at - Settlement.created_at) * 1000)
                .label("avg_latency_ms"),
            ).where(
                and_(
                    Settlement.merchant_id == merchant_id,
                    Settlement.provider_name == provider_name,
                    Settlement.settled_at >= day_start,
                    Settlement.settled_at < day_end,
                )
            )
        )

        settlement_row = settlement_result.first()
        settlement_count = settlement_row.total or 0 if settlement_row else 0
        settlement_success_count = settlement_count  # All settlements that exist are "successful"
        settlement_avg_latency_ms = int(settlement_row.avg_latency_ms or 0) if settlement_row else 0
        settlement_mismatch_count = 0  # Not tracked in current schema

        # Webhook metrics - using transaction events as proxy
        webhook_result = await db.execute(
            select(
                func.count(TransactionEvent.id).label("total"),
                func.sum(
                    case((TransactionEvent.status == "success", 1), else_=0)
                ).label("success_count"),
                func.sum(
                    case((TransactionEvent.status == "failed", 1), else_=0)
                ).label("fail_count"),
            )
            .select_from(TransactionEvent)
            .join(Transaction, TransactionEvent.transaction_id == Transaction.id)
            .where(
                and_(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider_name,
                    TransactionEvent.created_at >= day_start,
                    TransactionEvent.created_at < day_end,
                )
            )
        )

        webhook_row = webhook_result.first()
        webhook_event_count = webhook_row.total or 0 if webhook_row else 0
        webhook_success_count = webhook_row.success_count or 0 if webhook_row else 0
        webhook_fail_count = webhook_row.fail_count or 0 if webhook_row else 0
        webhook_avg_latency_ms = 0  # Not tracked in current schema

        # Calculate scores
        reliability_score_bps = await ProviderHealthService.calculate_reliability_score(
            db, merchant_id, provider_name
        )
        settlement_lag_score_bps = await ProviderHealthService.calculate_settlement_lag_score(
            db, merchant_id, provider_name
        )
        webhook_failure_score_bps = await ProviderHealthService.calculate_webhook_failure_score(
            db, merchant_id, provider_name
        )

        # Detect outages
        outage_windows = await ProviderHealthService.detect_outage_windows(
            db, merchant_id, provider_name
        )

        # Get health status
        health_status = await ProviderHealthService.get_health_status(
            db, merchant_id, provider_name, metric_date
        )

        # Create or update metric record
        existing = await db.execute(
            select(ProviderHealthMetrics).where(
                and_(
                    ProviderHealthMetrics.merchant_id == merchant_id,
                    ProviderHealthMetrics.provider_name == provider_name,
                    ProviderHealthMetrics.metric_date == metric_date,
                )
            )
        )
        metric = existing.scalars().first()

        if metric:
            metric.transaction_count = transaction_count
            metric.transaction_success_count = transaction_success_count
            metric.transaction_fail_count = transaction_fail_count
            metric.transaction_avg_latency_ms = transaction_avg_latency_ms
            metric.settlement_count = settlement_count
            metric.settlement_success_count = settlement_success_count
            metric.settlement_avg_latency_ms = settlement_avg_latency_ms
            metric.settlement_mismatch_count = settlement_mismatch_count
            metric.webhook_event_count = webhook_event_count
            metric.webhook_success_count = webhook_success_count
            metric.webhook_fail_count = webhook_fail_count
            metric.webhook_avg_latency_ms = webhook_avg_latency_ms
            metric.outage_windows = len(outage_windows)
            metric.reliability_score_bps = reliability_score_bps
            metric.settlement_lag_score_bps = settlement_lag_score_bps
            metric.webhook_failure_score_bps = webhook_failure_score_bps
            metric.health_status = health_status
        else:
            metric = ProviderHealthMetrics(
                merchant_id=merchant_id,
                provider_name=provider_name,
                metric_date=metric_date,
                transaction_count=transaction_count,
                transaction_success_count=transaction_success_count,
                transaction_fail_count=transaction_fail_count,
                transaction_avg_latency_ms=transaction_avg_latency_ms,
                settlement_count=settlement_count,
                settlement_success_count=settlement_success_count,
                settlement_avg_latency_ms=settlement_avg_latency_ms,
                settlement_mismatch_count=settlement_mismatch_count,
                webhook_event_count=webhook_event_count,
                webhook_success_count=webhook_success_count,
                webhook_fail_count=webhook_fail_count,
                webhook_avg_latency_ms=webhook_avg_latency_ms,
                outage_windows=len(outage_windows),
                reliability_score_bps=reliability_score_bps,
                settlement_lag_score_bps=settlement_lag_score_bps,
                webhook_failure_score_bps=webhook_failure_score_bps,
                health_status=health_status,
            )
            db.add(metric)

        return metric

    @staticmethod
    async def calculate_reliability_score(db: AsyncSession, merchant_id, provider_name: str) -> int:
        """7-day rolling success rate: (successes / total) * 10000."""
        seven_days_ago = datetime.now() - timedelta(days=7)

        result = await db.execute(
            select(
                func.count(Transaction.id).label("total"),
                func.sum(
                    case((Transaction.status == TransactionStatus.success.value, 1), else_=0)
                ).label("success_count"),
            ).where(
                and_(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider_name,
                    Transaction.created_at >= seven_days_ago,
                )
            )
        )

        row = result.first()
        total = row.total or 0 if row else 0
        success = row.success_count or 0 if row else 0

        if total == 0:
            return 10000  # Default to perfect score if no data

        return int((success / total) * 10000)

    @staticmethod
    async def calculate_settlement_lag_score(db: AsyncSession, merchant_id, provider_name: str) -> int:
        """Average settlement delay. Lower latency = higher score. Max score 10000."""
        result = await db.execute(
            select(Settlement.created_at, Settlement.settled_at).where(
                and_(
                    Settlement.merchant_id == merchant_id,
                    Settlement.provider_name == provider_name,
                )
            )
        )

        rows = result.fetchall()
        if not rows:
            return 10000  # Default to perfect score if no data

        # Calculate lag in seconds for each settlement
        lag_times = []
        for row in rows:
            created_at, settled_at = row
            if created_at and settled_at:
                lag_seconds = (settled_at - created_at).total_seconds()
                lag_times.append(lag_seconds)

        if not lag_times:
            return 10000

        avg_lag_seconds = sum(lag_times) / len(lag_times)

        # If settlement < 1 hour (3600s): 10000
        # If settlement > 24 hours: 0
        # Linear scale between
        if avg_lag_seconds <= 3600:
            return 10000
        if avg_lag_seconds >= 86400:  # 24 hours
            return 0

        # Linear interpolation: 10000 - (lag_seconds / 82800) * 10000
        return max(0, int(10000 - (avg_lag_seconds / 82800) * 10000))

    @staticmethod
    async def calculate_webhook_failure_score(db: AsyncSession, merchant_id, provider_name: str) -> int:
        """Webhook failure rate. Higher failures = lower score."""
        result = await db.execute(
            select(
                func.count(TransactionEvent.id).label("total"),
                func.sum(
                    case((TransactionEvent.status == "failed", 1), else_=0)
                ).label("fail_count"),
            )
            .select_from(TransactionEvent)
            .join(Transaction, TransactionEvent.transaction_id == Transaction.id)
            .where(
                and_(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider_name,
                )
            )
        )

        row = result.first()
        total = row.total or 0 if row else 0
        fail_count = row.fail_count or 0 if row else 0

        if total == 0:
            return 10000  # Default to perfect score if no data

        failure_rate = fail_count / total
        return int((1 - failure_rate) * 10000)

    @staticmethod
    async def detect_outage_windows(
        db: AsyncSession, merchant_id, provider_name: str
    ) -> list[dict]:
        """Find 1+ hour windows with 0% success rate."""
        # Get last 30 days of transactions
        thirty_days_ago = datetime.now() - timedelta(days=30)

        result = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.merchant_id == merchant_id,
                    Transaction.provider_name == provider_name,
                    Transaction.created_at >= thirty_days_ago,
                )
            )
        )

        transactions = result.scalars().all()

        # Group into hourly windows and find 100% failure windows
        outage_windows = []
        hourly_data = {}

        for tx in transactions:
            hour_key = tx.created_at.replace(minute=0, second=0, microsecond=0)
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {"total": 0, "success": 0}
            hourly_data[hour_key]["total"] += 1
            if tx.status == TransactionStatus.success.value:
                hourly_data[hour_key]["success"] += 1

        # Find consecutive hours with 0 success
        current_outage = None
        for hour_key in sorted(hourly_data.keys()):
            data = hourly_data[hour_key]
            if data["success"] == 0 and data["total"] > 0:
                if current_outage is None:
                    current_outage = {"start": hour_key, "end": hour_key}
                else:
                    current_outage["end"] = hour_key
            else:
                if current_outage is not None:
                    duration = (current_outage["end"] - current_outage["start"]).total_seconds() / 3600
                    if duration >= 1:  # At least 1 hour
                        outage_windows.append(
                            {
                                "start": current_outage["start"],
                                "end": current_outage["end"],
                                "duration_hours": duration,
                            }
                        )
                    current_outage = None

        # Handle last outage if it's still ongoing
        if current_outage is not None:
            duration = (current_outage["end"] - current_outage["start"]).total_seconds() / 3600
            if duration >= 1:
                outage_windows.append(
                    {
                        "start": current_outage["start"],
                        "end": current_outage["end"],
                        "duration_hours": duration,
                    }
                )

        return outage_windows

    @staticmethod
    async def get_health_status(
        db: AsyncSession, merchant_id, provider_name: str, metric_date: date = None
    ) -> str:
        """Classify as healthy/degraded/critical based on scores."""
        # Get latest metrics if no date specified
        if metric_date is None:
            metric_date = date.today()

        # Calculate current scores
        reliability_score_bps = await ProviderHealthService.calculate_reliability_score(
            db, merchant_id, provider_name
        )
        webhook_failure_score_bps = await ProviderHealthService.calculate_webhook_failure_score(
            db, merchant_id, provider_name
        )

        # Scoring logic:
        # Critical: reliability < 90% OR webhook failure > 50%
        # Degraded: reliability < 99% OR webhook failure > 10%
        # Healthy: otherwise
        if reliability_score_bps < 9000 or webhook_failure_score_bps < 5000:  # < 90%
            return HealthStatus.critical.value
        elif reliability_score_bps < 9900 or webhook_failure_score_bps < 9000:  # < 99% or > 10%
            return HealthStatus.degraded.value

        return HealthStatus.healthy.value
