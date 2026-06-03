import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.money_at_risk import MoneyAtRisk, MoneyAtRiskStatus
from ..models.transaction import Transaction, TransactionStatus
from ..models.reconciliation import ReconciliationResult, ReconciliationMatchStatus, Settlement
from ..models.alert import Alert, AlertStatus
from ..models.incident import Incident, IncidentStatus

logger = logging.getLogger("bomipay")


class MoneyAtRiskService:
    """Service for calculating and tracking Money-at-Risk (MAR) analytics.
    
    MAR tracks financial exposure from:
    - Pending transactions (age >= 30 minutes)
    - Unreconciled funds (age >= 7 days)
    - Failed transfers (age >= 1 day)
    """

    @staticmethod
    async def calculate_mar_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> dict:
        """Calculate daily MAR snapshot for a merchant.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            as_of_date: Date for the snapshot (defaults to today UTC)
            
        Returns:
            Dictionary with MAR calculations and breakdown
        """
        now = as_of_date or datetime.now(timezone.utc)
        period_date = now.date()
        
        # Calculate thresholds
        pending_cutoff = now - timedelta(minutes=30)
        unreconciled_cutoff = now - timedelta(days=7)
        failed_cutoff = now - timedelta(days=1)
        
        # === PENDING TRANSACTIONS ===
        pending_stmt = select(Transaction).where(
            and_(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.pending.value,
                Transaction.created_at <= pending_cutoff,
            )
        )
        pending_result = await db.execute(pending_stmt)
        pending_txns = list(pending_result.scalars().all())
        pending_amount = sum(Decimal(str(t.amount)) for t in pending_txns)
        pending_count = len(pending_txns)
        
        # === UNRECONCILED FUNDS ===
        # Get successful transactions older than 7 days that haven't been settled
        unreconciled_stmt = select(Transaction).where(
            and_(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.success.value,
                Transaction.created_at <= unreconciled_cutoff,
            )
        )
        unreconciled_result = await db.execute(unreconciled_stmt)
        unreconciled_txns = list(unreconciled_result.scalars().all())
        unreconciled_amount = sum(Decimal(str(t.amount)) for t in unreconciled_txns)
        unreconciled_count = len(unreconciled_txns)
        
        # === FAILED TRANSFERS ===
        failed_stmt = select(Transaction).where(
            and_(
                Transaction.merchant_id == merchant_id,
                Transaction.status == TransactionStatus.failed.value,
                Transaction.created_at <= failed_cutoff,
            )
        )
        failed_result = await db.execute(failed_stmt)
        failed_txns = list(failed_result.scalars().all())
        failed_amount = sum(Decimal(str(t.amount)) for t in failed_txns)
        failed_count = len(failed_txns)
        
        # Calculate total
        total_at_risk = pending_amount + unreconciled_amount + failed_amount
        
        # Calculate risk score (0-100)
        risk_score = MoneyAtRiskService._calculate_risk_score(
            pending_txns, unreconciled_txns, failed_txns, total_at_risk, now
        )
        
        # Breakdown by provider
        breakdown_by_provider = MoneyAtRiskService._breakdown_by_provider(
            pending_txns + unreconciled_txns + failed_txns
        )
        
        # Breakdown by status
        breakdown_by_status = {
            "pending": {"amount": float(pending_amount), "count": pending_count},
            "unreconciled": {"amount": float(unreconciled_amount), "count": unreconciled_count},
            "failed": {"amount": float(failed_amount), "count": failed_count},
        }
        
        return {
            "merchant_id": merchant_id,
            "period_date": period_date,
            "pending_transactions_amount": float(pending_amount),
            "pending_transactions_count": pending_count,
            "unreconciled_amount": float(unreconciled_amount),
            "unreconciled_transaction_count": unreconciled_count,
            "failed_transfers_amount": float(failed_amount),
            "failed_transfers_count": failed_count,
            "total_at_risk": float(total_at_risk),
            "risk_score": risk_score,
            "breakdown_by_provider": breakdown_by_provider,
            "breakdown_by_status": breakdown_by_status,
        }

    @staticmethod
    async def save_daily_snapshot(
        db: AsyncSession,
        merchant_id: str,
        as_of_date: Optional[datetime] = None,
    ) -> MoneyAtRisk:
        """Calculate and save daily MAR snapshot to database.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            as_of_date: Date for the snapshot (defaults to today UTC)
            
        Returns:
            MoneyAtRisk record
        """
        now = as_of_date or datetime.now(timezone.utc)
        period_date = now.date()
        
        # Calculate MAR data
        mar_data = await MoneyAtRiskService.calculate_mar_for_merchant(db, merchant_id, as_of_date=now)
        
        # Check if record for today already exists
        existing_stmt = select(MoneyAtRisk).where(
            and_(
                MoneyAtRisk.merchant_id == merchant_id,
                MoneyAtRisk.period_date == period_date,
            )
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalars().first()
        
        if existing:
            # Update existing record
            existing.pending_transactions_amount = Decimal(str(mar_data["pending_transactions_amount"]))
            existing.pending_transactions_count = mar_data["pending_transactions_count"]
            existing.unreconciled_amount = Decimal(str(mar_data["unreconciled_amount"]))
            existing.unreconciled_transaction_count = mar_data["unreconciled_transaction_count"]
            existing.failed_transfers_amount = Decimal(str(mar_data["failed_transfers_amount"]))
            existing.failed_transfers_count = mar_data["failed_transfers_count"]
            existing.total_at_risk = Decimal(str(mar_data["total_at_risk"]))
            existing.risk_score = mar_data["risk_score"]
            existing.breakdown_by_provider = mar_data["breakdown_by_provider"]
            existing.breakdown_by_status = mar_data["breakdown_by_status"]
            await db.flush()
            return existing
        else:
            # Create new record
            mar = MoneyAtRisk(
                merchant_id=merchant_id,
                period_date=period_date,
                pending_transactions_amount=Decimal(str(mar_data["pending_transactions_amount"])),
                pending_transactions_count=mar_data["pending_transactions_count"],
                unreconciled_amount=Decimal(str(mar_data["unreconciled_amount"])),
                unreconciled_transaction_count=mar_data["unreconciled_transaction_count"],
                failed_transfers_amount=Decimal(str(mar_data["failed_transfers_amount"])),
                failed_transfers_count=mar_data["failed_transfers_count"],
                total_at_risk=Decimal(str(mar_data["total_at_risk"])),
                risk_score=mar_data["risk_score"],
                breakdown_by_provider=mar_data["breakdown_by_provider"],
                breakdown_by_status=mar_data["breakdown_by_status"],
            )
            db.add(mar)
            await db.flush()
            return mar
    
    @staticmethod
    async def get_mar_trend(
        db: AsyncSession,
        merchant_id: str,
        days: int = 30,
        as_of_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get historical MAR trend for last N days.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            days: Number of days to retrieve (default 30)
            as_of_date: Reference date (defaults to today UTC)
            
        Returns:
            List of daily MAR snapshots ordered by date
        """
        now = as_of_date or datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)
        
        stmt = select(MoneyAtRisk).where(
            and_(
                MoneyAtRisk.merchant_id == merchant_id,
                MoneyAtRisk.period_date >= start_date.date(),
                MoneyAtRisk.period_date <= now.date(),
            )
        ).order_by(MoneyAtRisk.period_date.asc())
        
        result = await db.execute(stmt)
        records = result.scalars().all()
        
        return [
            {
                "period_date": str(r.period_date),
                "total_at_risk": float(r.total_at_risk),
                "risk_score": r.risk_score,
                "pending_amount": float(r.pending_transactions_amount),
                "unreconciled_amount": float(r.unreconciled_amount),
                "failed_amount": float(r.failed_transfers_amount),
            }
            for r in records
        ]

    @staticmethod
    async def identify_at_risk_transactions(
        db: AsyncSession,
        merchant_id: str,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List transactions contributing to MAR.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            category: Filter by category (pending, unreconciled, failed)
            limit: Maximum number of results
            
        Returns:
            List of at-risk transactions
        """
        now = datetime.now(timezone.utc)
        
        conditions = [Transaction.merchant_id == merchant_id]
        
        if category == "pending":
            conditions.extend([
                Transaction.status == TransactionStatus.pending.value,
                Transaction.created_at <= now - timedelta(minutes=30),
            ])
        elif category == "unreconciled":
            conditions.extend([
                Transaction.status == TransactionStatus.success.value,
                Transaction.created_at <= now - timedelta(days=7),
            ])
        elif category == "failed":
            conditions.extend([
                Transaction.status == TransactionStatus.failed.value,
                Transaction.created_at <= now - timedelta(days=1),
            ])
        else:
            # Get all at-risk transactions
            pending_cutoff = now - timedelta(minutes=30)
            unreconciled_cutoff = now - timedelta(days=7)
            failed_cutoff = now - timedelta(days=1)
            
            conditions = [
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_([
                    TransactionStatus.pending.value,
                    TransactionStatus.success.value,
                    TransactionStatus.failed.value,
                ]),
                (
                    (Transaction.status == TransactionStatus.pending.value and Transaction.created_at <= pending_cutoff) |
                    (Transaction.status == TransactionStatus.success.value and Transaction.created_at <= unreconciled_cutoff) |
                    (Transaction.status == TransactionStatus.failed.value and Transaction.created_at <= failed_cutoff)
                ),
            ]
        
        stmt = select(Transaction).where(and_(*conditions)).limit(limit).order_by(Transaction.created_at.desc())
        result = await db.execute(stmt)
        txns = result.scalars().all()
        
        return [
            {
                "id": str(t.id),
                "provider_name": t.provider_name,
                "provider_transaction_id": t.provider_transaction_id,
                "amount": t.amount,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "age_seconds": int((now - t.created_at).total_seconds()),
            }
            for t in txns
        ]

    @staticmethod
    def _calculate_risk_score(
        pending_txns: list,
        unreconciled_txns: list,
        failed_txns: list,
        total_at_risk: Decimal,
        now: datetime,
    ) -> int:
        """Calculate risk score (0-100) based on aging and volume.
        
        Factors:
        - Total amount at risk (weight: 30%)
        - Number of transactions (weight: 20%)
        - Age of pending transactions (weight: 25%)
        - Failed transaction count (weight: 15%)
        - Unreconciled age (weight: 10%)
        """
        # Ensure now is timezone-aware
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        
        score = 0
        
        # Factor 1: Total amount (scale to 0-30)
        amount_score = min(30, int((float(total_at_risk) / 1000000) * 30))
        score += amount_score
        
        # Factor 2: Transaction count (scale to 0-20)
        total_count = len(pending_txns) + len(unreconciled_txns) + len(failed_txns)
        count_score = min(20, total_count // 10)
        score += count_score
        
        # Factor 3: Age of pending transactions (scale to 0-25)
        if pending_txns:
            ages = []
            for t in pending_txns:
                created_at = t.created_at
                # Ensure created_at is timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                ages.append((now - created_at).total_seconds())
            avg_age_hours = sum(ages) / (3600 * len(pending_txns))
            age_score = min(25, int((avg_age_hours / 48) * 25))
            score += age_score
        
        # Factor 4: Failed transactions (scale to 0-15)
        failed_score = min(15, len(failed_txns) * 2)
        score += failed_score
        
        # Factor 5: Unreconciled age (scale to 0-10)
        if unreconciled_txns:
            days = []
            for t in unreconciled_txns:
                created_at = t.created_at
                # Ensure created_at is timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                days.append((now - created_at).days)
            avg_unreconciled_days = sum(days) / len(unreconciled_txns)
            unreconciled_score = min(10, int((avg_unreconciled_days / 30) * 10))
            score += unreconciled_score
        
        return min(100, score)

    @staticmethod
    def _breakdown_by_provider(txns: list) -> dict:
        """Break down at-risk amount by provider."""
        breakdown = {}
        for t in txns:
            provider = t.provider_name or "unknown"
            if provider not in breakdown:
                breakdown[provider] = {"amount": 0, "count": 0}
            breakdown[provider]["amount"] += t.amount
            breakdown[provider]["count"] += 1
        
        return {k: {"amount": float(v["amount"]), "count": v["count"]} for k, v in breakdown.items()}

    @staticmethod
    async def project_resolution(
        db: AsyncSession,
        merchant_id: str,
        days_ahead: int = 30,
    ) -> dict:
        """Estimate when MAR will clear based on historical trends.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            days_ahead: Number of days to project (default 30)
            
        Returns:
            Projection with estimated resolution date and risk timeline
        """
        # Get last 14 days of MAR data for trend analysis
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=14)
        
        stmt = select(MoneyAtRisk).where(
            and_(
                MoneyAtRisk.merchant_id == merchant_id,
                MoneyAtRisk.period_date >= start_date.date(),
            )
        ).order_by(MoneyAtRisk.period_date.asc())
        
        result = await db.execute(stmt)
        records = list(result.scalars().all())
        
        if not records:
            return {
                "estimated_resolution_date": None,
                "days_to_resolution": None,
                "projection": [],
                "confidence": "low",
                "reason": "Insufficient historical data",
                "daily_reduction_rate": 0.0,
            }
        
        # Calculate trend
        current_mar = float(records[-1].total_at_risk) if records else 0
        previous_mar = float(records[0].total_at_risk) if records else 0
        
        daily_reduction = (previous_mar - current_mar) / len(records) if len(records) > 0 else 0
        
        if daily_reduction <= 0:
            # MAR is not reducing or increasing
            return {
                "estimated_resolution_date": None,
                "days_to_resolution": None,
                "projection": [],
                "confidence": "low",
                "reason": "MAR is not decreasing",
                "daily_reduction_rate": daily_reduction,
            }
        
        # Project forward
        days_to_clear = int(current_mar / daily_reduction) if daily_reduction > 0 else None
        
        if days_to_clear is None or days_to_clear > days_ahead:
            estimated_date = None
            days_remaining = None
        else:
            estimated_date = (now + timedelta(days=days_to_clear)).date()
            days_remaining = days_to_clear
        
        # Generate projection timeline
        projection = []
        for day in range(min(days_ahead, days_to_clear + 1 if days_to_clear else days_ahead)):
            projected_mar = max(0, current_mar - (daily_reduction * day))
            projection.append({
                "day": day,
                "projected_date": (now + timedelta(days=day)).date().isoformat(),
                "projected_mar": projected_mar,
            })
        
        return {
            "estimated_resolution_date": estimated_date.isoformat() if estimated_date else None,
            "days_to_resolution": days_remaining,
            "projection": projection,
            "confidence": "medium" if len(records) >= 7 else "low",
            "daily_reduction_rate": daily_reduction,
        }

    @staticmethod
    async def get_alerts_for_high_mar(
        db: AsyncSession,
        merchant_id: str,
        mar_threshold: float = 1000000,  # 1M in minor units
        score_threshold: int = 70,
    ) -> list[dict]:
        """Alert if MAR exceeds threshold or trend is worsening.
        
        Args:
            db: Database session
            merchant_id: UUID of the merchant
            mar_threshold: Amount threshold for alert
            score_threshold: Risk score threshold for alert
            
        Returns:
            List of alerts with severity and recommendations
        """
        alerts = []
        
        # Get current MAR
        now = datetime.now(timezone.utc)
        current_mar_stmt = select(MoneyAtRisk).where(
            and_(
                MoneyAtRisk.merchant_id == merchant_id,
                MoneyAtRisk.period_date == now.date(),
            )
        )
        current_result = await db.execute(current_mar_stmt)
        current_mar = current_result.scalars().first()
        
        if not current_mar:
            return alerts
        
        current_total = float(current_mar.total_at_risk)
        current_score = current_mar.risk_score
        
        # Check if exceeds amount threshold
        if current_total > mar_threshold:
            alerts.append({
                "type": "high_amount",
                "severity": "high",
                "message": f"MAR exceeds threshold: {current_total:,.0f} > {mar_threshold:,.0f}",
                "amount": current_total,
                "recommendation": "Review pending and failed transactions; contact provider support",
            })
        
        # Check if exceeds score threshold
        if current_score > score_threshold:
            alerts.append({
                "type": "high_risk_score",
                "severity": "medium",
                "message": f"Risk score elevated: {current_score}",
                "score": current_score,
                "recommendation": "Investigate transaction patterns and aging analysis",
            })
        
        # Check for worsening trend
        yesterday_stmt = select(MoneyAtRisk).where(
            and_(
                MoneyAtRisk.merchant_id == merchant_id,
                MoneyAtRisk.period_date == (now - timedelta(days=1)).date(),
            )
        )
        yesterday_result = await db.execute(yesterday_stmt)
        yesterday_mar = yesterday_result.scalars().first()
        
        if yesterday_mar:
            yesterday_total = float(yesterday_mar.total_at_risk)
            if current_total > yesterday_total * 1.2:  # 20% increase
                alerts.append({
                    "type": "worsening_trend",
                    "severity": "medium",
                    "message": f"MAR increased 20%+ compared to yesterday",
                    "previous_amount": yesterday_total,
                    "current_amount": current_total,
                    "change_percent": ((current_total - yesterday_total) / yesterday_total * 100) if yesterday_total > 0 else 0,
                    "recommendation": "Investigate cause of increase; check provider status",
                })
        
        return alerts

    @staticmethod
    async def calculate(
        db: AsyncSession,
        merchant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        """Legacy method for backward compatibility.
        
        Compute daily MAR snapshot with all breakdowns.
        """
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

