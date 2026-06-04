import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.incident import Incident, IncidentEvent, IncidentStatus, IncidentSeverity

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
    async def get_by_id(db: AsyncSession, incident_id: str, include_events: bool = True) -> Optional[Incident]:
        stmt = select(Incident).where(Incident.id == incident_id)
        if include_events:
            stmt = stmt.options(joinedload(Incident.incident_events))
        result = await db.execute(stmt)
        return result.unique().scalar_one_or_none()

    @staticmethod
    async def list_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        incident_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_events: bool = False,
    ) -> list[Incident]:
        """List incidents for a merchant with optional eager loading.
        
        Note: If include_events=True, use pagination carefully as eager loading
        can cause cartesian product explosion. Default is False to avoid N+1 in
        favor of lazy loading events only when needed.
        """
        stmt = select(Incident).where(Incident.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        if incident_type:
            stmt = stmt.where(Incident.incident_type == incident_type)
        if include_events:
            stmt = stmt.options(joinedload(Incident.incident_events))
        stmt = stmt.order_by(Incident.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

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

    @staticmethod
    async def auto_escalate_if_needed(
        db: AsyncSession,
        incident: Incident,
        actor_user_id: Optional[str] = None,
    ) -> Incident:
        """Auto-escalate incident based on duration or pattern.
        
        Rules:
        - Escalate if open/investigating for >1 hour and severity < critical
        - Escalate if multiple incidents of same type within 6 hours
        """
        if incident.status not in (IncidentStatus.open.value, IncidentStatus.investigating.value):
            return incident
        
        now = datetime.now(timezone.utc)
        time_since_creation = now - incident.created_at
        
        # Rule 1: Escalate if open for >1 hour
        if time_since_creation > timedelta(hours=1):
            if incident.severity != IncidentSeverity.critical.value:
                old_severity = incident.severity
                incident.severity = IncidentSeverity.critical.value
                await db.flush()
                await IncidentService._append_event(
                    db, incident.id, "escalated", actor_user_id,
                    f"Incident automatically escalated from {old_severity} to critical due to duration",
                    {"previous_severity": old_severity, "reason": "open_duration_exceeded_1h"},
                )
        
        # Rule 2: Check for multiple incidents of same type within 6 hours
        six_hours_ago = now - timedelta(hours=6)
        stmt = select(func.count(Incident.id)).where(
            and_(
                Incident.merchant_id == incident.merchant_id,
                Incident.incident_type == incident.incident_type,
                Incident.created_at >= six_hours_ago,
                Incident.id != incident.id,
            )
        )
        result = await db.execute(stmt)
        similar_count = result.scalar()
        
        if similar_count and similar_count >= 2 and incident.severity not in (
            IncidentSeverity.high.value,
            IncidentSeverity.critical.value,
        ):
            old_severity = incident.severity
            incident.severity = IncidentSeverity.high.value
            await db.flush()
            await IncidentService._append_event(
                db, incident.id, "escalated", actor_user_id,
                f"Incident escalated to high due to multiple similar incidents",
                {"previous_severity": old_severity, "reason": "pattern_detected", "similar_count": similar_count},
            )
        
        return incident

    @staticmethod
    async def get_statistics(
        db: AsyncSession,
        merchant_id: str,
    ) -> dict:
        """Get incident statistics for a merchant."""
        stmt_total = select(func.count(Incident.id)).where(Incident.merchant_id == merchant_id)
        result = await db.execute(stmt_total)
        total_incidents = result.scalar() or 0
        
        # Count by status
        statuses = {}
        for status in IncidentStatus:
            stmt = select(func.count(Incident.id)).where(
                and_(Incident.merchant_id == merchant_id, Incident.status == status.value)
            )
            result = await db.execute(stmt)
            statuses[status.value] = result.scalar() or 0
        
        # Count by severity
        severities = {}
        for severity in IncidentSeverity:
            stmt = select(func.count(Incident.id)).where(
                and_(Incident.merchant_id == merchant_id, Incident.severity == severity.value)
            )
            result = await db.execute(stmt)
            severities[severity.value] = result.scalar() or 0
        
        # Count by type
        stmt_types = select(Incident.incident_type, func.count(Incident.id)).where(
            Incident.merchant_id == merchant_id
        ).group_by(Incident.incident_type)
        result = await db.execute(stmt_types)
        types = {row[0]: row[1] for row in result.all()}
        
        # Average resolution time (for resolved incidents)
        stmt_avg = select(func.avg(Incident.ended_at - Incident.created_at)).where(
            and_(
                Incident.merchant_id == merchant_id,
                Incident.ended_at.is_not(None),
            )
        )
        result = await db.execute(stmt_avg)
        avg_duration = result.scalar()
        avg_resolution_time_seconds = int(avg_duration.total_seconds()) if avg_duration else None
        
        # Critical incidents in last 24 hours
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt_critical = select(func.count(Incident.id)).where(
            and_(
                Incident.merchant_id == merchant_id,
                Incident.severity == IncidentSeverity.critical.value,
                Incident.created_at >= twenty_four_hours_ago,
            )
        )
        result = await db.execute(stmt_critical)
        critical_in_24h = result.scalar() or 0
        
        return {
            "total_incidents": total_incidents,
            "by_status": statuses,
            "by_severity": severities,
            "by_type": types,
            "avg_resolution_time_seconds": avg_resolution_time_seconds,
            "critical_incidents_24h": critical_in_24h,
        }
