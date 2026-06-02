from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog


def log_audit_event(
    db: AsyncSession,
    event_type: str,
    actor_id: str | None = None,
    actor_role: str | None = None,
    event_payload: dict | None = None,
    source: str = "api",
) -> None:
    audit = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=event_type,
        event_payload=event_payload,
        source=source,
    )
    db.add(audit)
