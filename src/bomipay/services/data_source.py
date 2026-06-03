import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.data_source import DataSource, DataSourceStatus

logger = logging.getLogger("bomipay")


class DataSourceService:
    @staticmethod
    async def create(
        db: AsyncSession,
        merchant_id: str,
        source_type: str,
        display_name: str,
        provider_name: Optional[str] = None,
        configuration_json: Optional[dict] = None,
    ) -> DataSource:
        ds = DataSource(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_type=source_type,
            provider_name=provider_name,
            display_name=display_name,
            configuration_json=configuration_json,
        )
        db.add(ds)
        await db.flush()
        logger.info("data_source.created", extra={"data_source_id": str(ds.id), "merchant_id": str(merchant_id)})
        return ds

    @staticmethod
    async def list_for_merchant(db: AsyncSession, merchant_id: str) -> list[DataSource]:
        result = await db.execute(
            select(DataSource).where(DataSource.merchant_id == merchant_id).order_by(DataSource.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, data_source_id: str) -> Optional[DataSource]:
        result = await db.execute(select(DataSource).where(DataSource.id == data_source_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, ds: DataSource, updates: dict) -> DataSource:
        for field, value in updates.items():
            if value is not None and hasattr(ds, field):
                setattr(ds, field, value)
        await db.flush()
        return ds

    @staticmethod
    async def mark_sync_attempted(db: AsyncSession, ds: DataSource, success: bool, error: Optional[str] = None) -> DataSource:
        now = datetime.now(timezone.utc)
        ds.last_sync_at = now
        if success:
            ds.last_success_at = now
            ds.status = DataSourceStatus.active.value
        else:
            ds.last_error_at = now
            ds.last_error_message = error
            ds.status = DataSourceStatus.error.value
        await db.flush()
        return ds

    @staticmethod
    async def upsert_webhook_source(
        db: AsyncSession,
        merchant_id: str,
        provider_name: str,
    ) -> DataSource:
        result = await db.execute(
            select(DataSource).where(
                DataSource.merchant_id == merchant_id,
                DataSource.source_type == "provider_webhook",
                DataSource.provider_name == provider_name,
            )
        )
        ds = result.scalar_one_or_none()
        if ds is None:
            ds = DataSource(
                id=uuid.uuid4(),
                merchant_id=merchant_id,
                source_type="provider_webhook",
                provider_name=provider_name,
                display_name=f"{provider_name} Webhook",
                status=DataSourceStatus.active.value,
            )
            db.add(ds)
        else:
            ds.status = DataSourceStatus.active.value
        await db.flush()
        return ds

    @staticmethod
    def derive_health(ds: DataSource) -> str:
        if ds.status == DataSourceStatus.active.value:
            return "healthy"
        if ds.status == DataSourceStatus.error.value:
            return "degraded"
        if ds.status == DataSourceStatus.pending_setup.value:
            return "pending"
        return "inactive"
