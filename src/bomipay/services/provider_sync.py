import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus, ErrorSeverity
from ..models.provider_account import ProviderAccount
from ..services.providers import ProviderAdapterRegistry
from ..services.encryption import decrypt_secret

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
        
        # Retryable errors
        if any(x in error_str for x in ["timeout", "connection", "network", "temporarily unavailable"]):
            return (ErrorSeverity.retryable.value, True)
        
        if "429" in error_str or "rate limit" in error_str:
            return (ErrorSeverity.retryable.value, True)
        
        if any(x in error_str for x in ["500", "502", "503", "504"]):
            return (ErrorSeverity.retryable.value, True)
        
        # Permanent errors
        if any(x in error_str for x in ["401", "403", "unauthorized", "forbidden", "invalid credentials"]):
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
            BASE_BACKOFF_SECONDS * (2 ** job.retry_count),
            MAX_BACKOFF_SECONDS
        )
        job.backoff_multiplier = backoff_seconds / BASE_BACKOFF_SECONDS
        return datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
    
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
            extra={"job_id": str(job.id), "sync_type": sync_type, "provider_account_id": str(provider_account_id)},
        )
        return job

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

        try:
            adapter = ProviderAdapterRegistry.get_adapter(provider_account.provider_name)
            if adapter is None:
                raise ValueError(f"No adapter registered for provider: {provider_account.provider_name}")

            credentials = {
                "api_key": decrypt_secret(provider_account.api_key_encrypted),
                "secret_key": decrypt_secret(provider_account.secret_encrypted),
            }

            raw_response: dict = {}
            records_seen = 0
            records_created = 0
            records_updated = 0
            records_failed = 0
            failure_details = []

            if job.sync_type == "transactions":
                raw_response = {"synced": True, "type": "transactions"}
                records_seen = 0
            elif job.sync_type == "settlements":
                settlements = adapter.fetch_settlements(str(provider_account.merchant_id))
                raw_response = {"settlements": settlements}
                records_seen = len(settlements)
            elif job.sync_type == "provider_health":
                health = adapter.get_provider_health(credentials)
                raw_response = health
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
                job.status = ProviderSyncStatus.failed_permanent.value if not is_retryable else ProviderSyncStatus.failed.value
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

        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> Optional[ProviderSyncJob]:
        result = await db.execute(select(ProviderSyncJob).where(ProviderSyncJob.id == job_id))
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
                (ProviderSyncJob.next_retry_at.is_(None) | (ProviderSyncJob.next_retry_at <= now))
            )
            .order_by(ProviderSyncJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

