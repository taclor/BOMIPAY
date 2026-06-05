import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus, ErrorSeverity
from ..models.provider_account import ProviderAccount
from ..models.transaction import Transaction, TransactionStatus
from ..services.providers import ProviderAdapterRegistry
from ..services.encryption import decrypt_secret
from ..services.provider_normalize import ProviderNormalizer
from ..services.settlement import upsert_settlement
from ..services.provider_adapters_async import (
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthError,
)
from ..services.adapters.registry import get_adapter as _get_new_adapter

logger = logging.getLogger("bomipay")

# Configuration
BASE_BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 3600  # 1 hour
DEFAULT_MAX_RETRIES = 3


class ProviderSyncService:
    @staticmethod
    def _classify_error(error: Exception) -> Tuple[str, bool]:
        """
        Classify error as retryable or permanent.
        Returns: (severity: str, is_retryable: bool)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Provider-specific retryable errors
        if isinstance(error, ProviderTimeoutError):
            return (ErrorSeverity.retryable.value, True)
        if isinstance(error, ProviderRateLimitError):
            return (ErrorSeverity.retryable.value, True)
        if isinstance(error, ProviderAuthError):
            return (ErrorSeverity.permanent.value, False)

        # Retryable errors
        if any(
            x in error_str
            for x in ["timeout", "connection", "network", "temporarily unavailable"]
        ):
            return (ErrorSeverity.retryable.value, True)

        if "429" in error_str or "rate limit" in error_str:
            return (ErrorSeverity.retryable.value, True)

        if any(x in error_str for x in ["500", "502", "503", "504"]):
            return (ErrorSeverity.retryable.value, True)

        # Permanent errors
        if any(
            x in error_str
            for x in ["401", "403", "unauthorized", "forbidden", "invalid credentials"]
        ):
            return (ErrorSeverity.permanent.value, False)

        if "404" in error_str or "not found" in error_str:
            return (ErrorSeverity.permanent.value, False)

        if any(x in error_str for x in ["400", "validation", "invalid"]):
            return (ErrorSeverity.permanent.value, False)

        # Default to retryable with caution
        return (ErrorSeverity.unknown.value, True)

    @staticmethod
    def _calculate_next_retry(job: ProviderSyncJob) -> datetime:
        """Calculate next retry time using exponential backoff."""
        # Exponential backoff: 2^retry_count * BASE_BACKOFF_SECONDS
        backoff_seconds = min(
            BASE_BACKOFF_SECONDS * (2 ** job.retry_count), MAX_BACKOFF_SECONDS
        )
        job.backoff_multiplier = backoff_seconds / BASE_BACKOFF_SECONDS
        return datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

    @staticmethod
    def _get_adapter(provider_name: str, api_key: str, secret_key: str = ""):
        """Get the appropriate adapter for the provider."""
        return _get_new_adapter(provider_name, api_key=api_key, secret_key=secret_key or None)

    @staticmethod
    async def create_job(
        db: AsyncSession,
        merchant_id: str,
        provider_account_id: str,
        sync_type: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
    ) -> ProviderSyncJob:
        job = ProviderSyncJob(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            provider_account_id=provider_account_id,
            sync_type=sync_type,
            status=ProviderSyncStatus.queued.value,
            date_from=date_from,
            date_to=date_to,
            correlation_id=correlation_id or str(uuid.uuid4()),
            max_retries=DEFAULT_MAX_RETRIES,
        )
        db.add(job)
        await db.flush()
        logger.info(
            "provider_sync.job_created",
            extra={
                "job_id": str(job.id),
                "sync_type": sync_type,
                "provider_account_id": str(provider_account_id),
            },
        )
        return job

    @staticmethod
    async def _sync_transactions(
        adapter,
        db: AsyncSession,
        merchant_id: str,
        provider_account: ProviderAccount,
        date_from: datetime,
        date_to: datetime,
    ) -> Tuple[int, int, int, list]:
        """Sync transactions from provider."""
        records_seen = 0
        records_created = 0
        records_updated = 0
        failure_details = []

        try:
            adapter_transactions = await adapter.fetch_transactions(date_from, date_to)
            records_seen = len(adapter_transactions)

            for adapter_txn in adapter_transactions:
                try:
                    # Use raw_payload so existing ProviderNormalizer logic is preserved
                    normalized = ProviderNormalizer.normalize_transaction(
                        provider_account.provider_name, adapter_txn.raw_payload
                    )

                    provider_txn_id = normalized["provider_transaction_id"]

                    # Check for duplicate
                    result = await db.execute(
                        select(Transaction).where(
                            Transaction.merchant_id == merchant_id,
                            Transaction.provider_transaction_id == provider_txn_id,
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update existing transaction
                        existing.status = normalized["status"]
                        existing.amount = normalized["amount"]
                        existing.currency = normalized["currency"]
                        existing.customer_email = normalized.get("customer_email")
                        if normalized.get("timestamp"):
                            existing.initiated_at = normalized["timestamp"]
                        records_updated += 1
                    else:
                        # Create new transaction
                        txn = Transaction(
                            id=uuid.uuid4(),
                            merchant_id=merchant_id,
                            provider_name=provider_account.provider_name,
                            provider_transaction_id=provider_txn_id,
                            currency=normalized["currency"],
                            amount=normalized["amount"],
                            status=normalized["status"],
                            customer_email=normalized.get("customer_email"),
                            initiated_at=normalized.get("timestamp"),
                        )
                        db.add(txn)
                        records_created += 1

                except Exception as e:
                    failure_details.append(
                        {
                            "record_id": adapter_txn.provider_transaction_id,
                            "error": str(e)[:255],
                            "severity": "warning",
                        }
                    )

            await db.flush()

        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            raise

        return records_seen, records_created, records_updated, failure_details

    @staticmethod
    async def _sync_settlements(
        adapter,
        db: AsyncSession,
        merchant_id: str,
        provider_account: ProviderAccount,
        date_from: datetime,
        date_to: datetime,
    ) -> Tuple[int, int, int, list]:
        """Sync settlements from provider."""
        records_seen = 0
        records_created = 0
        records_updated = 0
        failure_details = []

        try:
            adapter_settlements = await adapter.fetch_settlements(date_from, date_to)
            records_seen = len(adapter_settlements)

            for adapter_settlement in adapter_settlements:
                try:
                    normalized = ProviderNormalizer.normalize_settlement(
                        provider_account.provider_name, adapter_settlement.raw_payload
                    )
                    await upsert_settlement(
                        db=db,
                        merchant_id=str(provider_account.merchant_id),
                        provider_name=provider_account.provider_name,
                        reference=normalized.get("settlement_reference") or adapter_settlement.provider_settlement_id,
                        amount_minor=normalized.get("amount", 0),
                        currency=normalized.get("currency", "NGN"),
                        status=normalized.get("status", "settled"),
                        settled_at=normalized.get("settled_at"),
                        expected_arrival_at=normalized.get("expected_arrival_at"),
                        raw_payload=adapter_settlement.raw_payload,
                        provider_account_id=str(provider_account.id),
                    )
                    records_created += 1
                except Exception as e:
                    failure_details.append(
                        {
                            "record_id": adapter_settlement.provider_settlement_id,
                            "error": str(e)[:255],
                            "severity": "warning",
                        }
                    )

        except Exception as e:
            logger.error(f"Error fetching settlements: {e}")
            raise

        return records_seen, records_created, records_updated, failure_details

    @staticmethod
    async def _sync_transfers(
        adapter,
        db: AsyncSession,
        merchant_id: str,
        provider_account: ProviderAccount,
        date_from: datetime,
        date_to: datetime,
    ) -> Tuple[int, int, int, list]:
        """Sync transfers from provider."""
        records_seen = 0
        records_created = 0
        records_updated = 0
        failure_details = []

        try:
            raw_transfers = await adapter.fetch_transfers(date_from, date_to)
            records_seen = len(raw_transfers)
            for raw_transfer in raw_transfers:
                try:
                    normalized = ProviderNormalizer.normalize_transfer(
                        provider_account.provider_name, raw_transfer
                    )
                    records_created += 1
                except Exception as e:
                    failure_details.append(
                        {
                            "record_id": raw_transfer.get("id")
                            or raw_transfer.get("reference"),
                            "error": str(e)[:255],
                            "severity": "warning",
                        }
                    )

        except Exception as e:
            logger.error(f"Error fetching transfers: {e}")
            raise

        return records_seen, records_created, records_updated, failure_details

    @staticmethod
    async def _sync_refunds(
        adapter,
        db: AsyncSession,
        merchant_id: str,
        provider_account: ProviderAccount,
        transaction_id: str,
    ) -> Tuple[int, int, int, list]:
        """Sync refunds for a transaction from provider."""
        records_seen = 0
        records_created = 0
        records_updated = 0
        failure_details = []

        try:
            raw_refunds = await adapter.fetch_refunds()
            records_seen = len(raw_refunds)

            for raw_refund in raw_refunds:
                try:
                    normalized = ProviderNormalizer.normalize_refund(
                        provider_account.provider_name, raw_refund
                    )
                    records_created += 1
                except Exception as e:
                    failure_details.append(
                        {
                            "record_id": raw_refund.get("id")
                            or raw_refund.get("reference"),
                            "error": str(e)[:255],
                            "severity": "warning",
                        }
                    )

        except Exception as e:
            logger.error(f"Error fetching refunds: {e}")
            raise

        return records_seen, records_created, records_updated, failure_details

    @staticmethod
    async def run_job(
        db: AsyncSession,
        job: ProviderSyncJob,
        provider_account: ProviderAccount,
    ) -> ProviderSyncJob:
        """Run sync job with retry and partial failure handling."""
        job.status = ProviderSyncStatus.running.value
        job.started_at = datetime.now(timezone.utc)
        await db.flush()

        adapter = None
        try:
            api_key = decrypt_secret(provider_account.api_key_encrypted)
            secret_key = decrypt_secret(provider_account.secret_encrypted) if provider_account.secret_encrypted else ""

            adapter = ProviderSyncService._get_adapter(
                provider_account.provider_name, api_key, secret_key
            )

            raw_response: dict = {}
            records_seen = 0
            records_created = 0
            records_updated = 0
            records_failed = 0
            failure_details = []

            date_from = job.date_from or (datetime.now(timezone.utc) - timedelta(days=30))
            date_to = job.date_to or datetime.now(timezone.utc)

            if job.sync_type == "transactions":
                seen, created, updated, failures = await ProviderSyncService._sync_transactions(
                    adapter, db, str(provider_account.merchant_id), provider_account, date_from, date_to
                )
                records_seen = seen
                records_created = created
                records_updated = updated
                failure_details = failures
                raw_response = {"synced": True, "type": "transactions", "records": seen}

            elif job.sync_type == "settlements":
                seen, created, updated, failures = await ProviderSyncService._sync_settlements(
                    adapter, db, str(provider_account.merchant_id), provider_account, date_from, date_to
                )
                records_seen = seen
                records_created = created
                records_updated = updated
                failure_details = failures
                raw_response = {"synced": True, "type": "settlements", "records": seen}

            elif job.sync_type == "transfers":
                seen, created, updated, failures = await ProviderSyncService._sync_transfers(
                    adapter, db, str(provider_account.merchant_id), provider_account, date_from, date_to
                )
                records_seen = seen
                records_created = created
                records_updated = updated
                failure_details = failures
                raw_response = {"synced": True, "type": "transfers", "records": seen}

            elif job.sync_type == "provider_health":
                health = await adapter.get_provider_health()
                # Convert ProviderHealthStatus dataclass to serialisable dict
                raw_response = {
                    "status": "ok" if health.is_healthy else "degraded",
                    "latency_ms": health.latency_ms,
                    "timestamp": health.last_checked_at.isoformat(),
                    "error": health.error_message,
                }
                records_seen = 1

            else:
                raw_response = {"synced": True, "type": job.sync_type}

            job.raw_response_json = raw_response
            job.records_seen = records_seen
            job.records_created = records_created
            job.records_updated = records_updated
            job.records_failed = records_failed
            job.failure_details = failure_details if failure_details else None
            job.status = ProviderSyncStatus.completed.value
            job.completed_at = datetime.now(timezone.utc)
            job.retry_count = 0  # Reset retry count on success
            logger.info(
                "provider_sync.job_completed",
                extra={
                    "job_id": str(job.id),
                    "records_seen": records_seen,
                    "created": records_created,
                    "updated": records_updated,
                    "failed": records_failed,
                },
            )

        except Exception as exc:
            severity, is_retryable = ProviderSyncService._classify_error(exc)
            error_msg = str(exc)[:1024]

            job.error_message = error_msg
            job.error_severity = severity
            job.completed_at = datetime.now(timezone.utc)

            # Determine if we should retry
            if is_retryable and job.retry_count < job.max_retries:
                job.status = ProviderSyncStatus.queued.value
                job.retry_count += 1
                job.next_retry_at = ProviderSyncService._calculate_next_retry(job)
                logger.warning(
                    "provider_sync.job_retryable",
                    extra={
                        "job_id": str(job.id),
                        "retry": job.retry_count,
                        "max_retries": job.max_retries,
                        "next_retry_at": job.next_retry_at.isoformat(),
                        "error": error_msg,
                        "severity": severity,
                    },
                )
            else:
                # Permanent failure or max retries exceeded
                job.status = (
                    ProviderSyncStatus.failed_permanent.value
                    if not is_retryable
                    else ProviderSyncStatus.failed.value
                )
                logger.error(
                    "provider_sync.job_failed",
                    extra={
                        "job_id": str(job.id),
                        "retry": job.retry_count,
                        "max_retries": job.max_retries,
                        "error": error_msg,
                        "severity": severity,
                    },
                )

        finally:
            # Clean up adapter resources
            if adapter:
                try:
                    await adapter.close()
                except Exception as e:
                    logger.debug(f"Error closing adapter: {e}")

        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> Optional[ProviderSyncJob]:
        result = await db.execute(
            select(ProviderSyncJob).where(ProviderSyncJob.id == job_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_jobs_for_provider_account(
        db: AsyncSession,
        provider_account_id: str,
        merchant_id: str,
        limit: int = 50,
    ) -> list[ProviderSyncJob]:
        result = await db.execute(
            select(ProviderSyncJob)
            .where(
                ProviderSyncJob.provider_account_id == provider_account_id,
                ProviderSyncJob.merchant_id == merchant_id,
            )
            .order_by(ProviderSyncJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_pending_jobs(
        db: AsyncSession,
        limit: int = 100,
    ) -> list[ProviderSyncJob]:
        """Get jobs that need to be retried (queued with next_retry_at in past)."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ProviderSyncJob)
            .where(
                ProviderSyncJob.status == ProviderSyncStatus.queued.value,
                (
                    ProviderSyncJob.next_retry_at.is_(None)
                    | (ProviderSyncJob.next_retry_at <= now)
                ),
            )
            .order_by(ProviderSyncJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
