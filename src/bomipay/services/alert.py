from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.alert import Alert, AlertSeverity, AlertType


class AlertService:
    @staticmethod
    async def create_alert(
        db: AsyncSession,
        merchant_id,
        alert_type: AlertType,
        severity: AlertSeverity,
        description: str,
        transaction_id=None,
        source_event_id: str | None = None,
        metadata_json: dict | None = None,
    ) -> Alert:
        if source_event_id:
            existing = await AlertService.get_by_source_event(db, merchant_id, source_event_id, alert_type)
            if existing:
                return existing

        alert = Alert(
            merchant_id=merchant_id,
            transaction_id=transaction_id,
            source_event_id=source_event_id,
            alert_type=alert_type.value,
            severity=severity.value,
            description=description,
            metadata_json=metadata_json,
        )
        db.add(alert)
        await db.flush()
        await db.refresh(alert)
        return alert

    @staticmethod
    async def get_by_source_event(
        db: AsyncSession, merchant_id, source_event_id: str, alert_type: AlertType
    ) -> Alert | None:
        result = await db.execute(
            select(Alert)
            .where(Alert.merchant_id == merchant_id)
            .where(Alert.source_event_id == source_event_id)
            .where(Alert.alert_type == alert_type.value)
        )
        return result.scalars().first()

    @staticmethod
    async def list_alerts(db: AsyncSession, merchant_id, filters: dict) -> list[Alert]:
        query = select(Alert).where(Alert.merchant_id == merchant_id)
        if status := filters.get("status"):
            query = query.where(Alert.status == status)
        if severity := filters.get("severity"):
            query = query.where(Alert.severity == severity)
        if alert_type := filters.get("alert_type"):
            query = query.where(Alert.alert_type == alert_type)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_alert_status(db: AsyncSession, alert: Alert, status: str) -> Alert:
        alert.status = status
        await db.flush()
        await db.refresh(alert)
        return alert
