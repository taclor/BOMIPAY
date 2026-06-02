import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus
from ..models.provider_account import ProviderAccount
from ..services.providers import ProviderAdapterRegistry
from ..services.encryption import decrypt_secret

logger = logging.getLogger("bomipay")


class ProviderSyncService:
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
            job.status = ProviderSyncStatus.completed.value
            job.completed_at = datetime.now(timezone.utc)
            logger.info("provider_sync.job_completed", extra={"job_id": str(job.id), "records_seen": records_seen})

        except Exception as exc:
            job.status = ProviderSyncStatus.failed.value
            job.error_message = str(exc)[:1024]
            job.completed_at = datetime.now(timezone.utc)
            logger.error("provider_sync.job_failed", extra={"job_id": str(job.id), "error": str(exc)})

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
