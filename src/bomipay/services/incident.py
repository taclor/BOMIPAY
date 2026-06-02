import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.incident import Incident, IncidentEvent, IncidentStatus

logger = logging.getLogger("bomipay")


class IncidentService:
    @staticmethod
    async def create(
        db: AsyncSession,
        merchant_id: str,
        title: str,
        incident_type: str,
        severity: str,
        started_at: datetime,
        summary: str,
        provider_name: Optional[str] = None,
        affected_amount_minor: int = 0,
        affected_transaction_count: int = 0,
    ) -> Incident:
        incident = Incident(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            title=title,
            incident_type=incident_type,
            severity=severity,
            status=IncidentStatus.open.value,
            provider_name=provider_name,
            affected_amount_minor=affected_amount_minor,
            affected_transaction_count=affected_transaction_count,
            started_at=started_at,
            summary=summary,
        )
        db.add(incident)
        await db.flush()

        await IncidentService._append_event(
            db, incident.id, "incident_created", None,
            f"Incident created: {title}", {}
        )
        logger.info("incident.created", extra={"incident_id": str(incident.id), "merchant_id": str(merchant_id)})
        return incident

    @staticmethod
    async def get_by_id(db: AsyncSession, incident_id: str) -> Optional[Incident]:
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Incident]:
        stmt = select(Incident).where(Incident.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        stmt = stmt.order_by(Incident.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def acknowledge(
        db: AsyncSession,
        incident: Incident,
        actor_user_id: Optional[str],
    ) -> Incident:
        incident.status = IncidentStatus.acknowledged.value
        await db.flush()
        await IncidentService._append_event(
            db, incident.id, "acknowledged", actor_user_id,
            "Incident acknowledged", {}
        )
        return incident

    @staticmethod
    async def resolve(
        db: AsyncSession,
        incident: Incident,
        actor_user_id: Optional[str],
        resolution_note: Optional[str] = None,
    ) -> Incident:
        incident.status = IncidentStatus.resolved.value
        incident.ended_at = datetime.now(timezone.utc)
        await db.flush()
        await IncidentService._append_event(
            db, incident.id, "resolved", actor_user_id,
            resolution_note or "Incident resolved", {}
        )
        return incident

    @staticmethod
    async def add_event(
        db: AsyncSession,
        incident: Incident,
        event_type: str,
        actor_user_id: Optional[str],
        message: str,
        metadata_json: Optional[dict] = None,
    ) -> IncidentEvent:
        return await IncidentService._append_event(
            db, incident.id, event_type, actor_user_id, message, metadata_json
        )

    @staticmethod
    async def _append_event(
        db: AsyncSession,
        incident_id,
        event_type: str,
        actor_user_id: Optional[str],
        message: str,
        metadata_json: Optional[dict],
    ) -> IncidentEvent:
        event = IncidentEvent(
            id=uuid.uuid4(),
            incident_id=incident_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            message=message,
            metadata_json=metadata_json,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def update(
        db: AsyncSession,
        incident: Incident,
        updates: dict,
        actor_user_id: Optional[str] = None,
    ) -> Incident:
        for field, value in updates.items():
            if value is not None and hasattr(incident, field):
                setattr(incident, field, value)
        await db.flush()
        await IncidentService._append_event(
            db, incident.id, "updated", actor_user_id,
            "Incident updated", updates
        )
        return incident

    @staticmethod
    async def list_events(db: AsyncSession, incident_id: str) -> list[IncidentEvent]:
        result = await db.execute(
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at)
        )
        return list(result.scalars().all())
