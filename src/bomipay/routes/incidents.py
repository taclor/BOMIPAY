import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.incident import (
    IncidentCreate,
    IncidentEventCreate,
    IncidentEventResponse,
    IncidentResponse,
    IncidentUpdate,
)
from ..services.audit import log_audit_event
from ..services.auth import require_role
from ..services.incident import IncidentService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Incidents"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance, Role.support)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    merchant_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    incidents = await IncidentService.list_for_merchant(
        db, effective, status=status, severity=severity, limit=limit, offset=offset
    )
    return [IncidentResponse.model_validate(i) for i in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    incident = await IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    _check_merchant_access(current_user, str(incident.merchant_id))
    return IncidentResponse.model_validate(incident)


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    current_user=Depends(require_role(Role.admin, Role.finance)),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = str(payload.merchant_id or current_user.merchant_id or "")
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)
    incident = await IncidentService.create(
        db,
        merchant_id=merchant_id,
        title=payload.title,
        incident_type=payload.incident_type,
        severity=payload.severity,
        started_at=payload.started_at,
        summary=payload.summary,
        provider_name=payload.provider_name,
        affected_amount_minor=payload.affected_amount_minor,
        affected_transaction_count=payload.affected_transaction_count,
    )
    log_audit_event(
        db,
        event_type="incident.created",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"incident_id": str(incident.id)},
    )
    await db.commit()
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/acknowledge", response_model=IncidentResponse)
async def acknowledge_incident(
    incident_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    incident = await IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    _check_merchant_access(current_user, str(incident.merchant_id))
    incident = await IncidentService.acknowledge(db, incident, str(current_user.id))
    log_audit_event(
        db,
        event_type="incident.acknowledged",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"incident_id": incident_id},
    )
    await db.refresh(incident)
    await db.commit()
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: str,
    resolution_note: Optional[str] = None,
    current_user=Depends(require_role(Role.admin, Role.finance)),
    db: AsyncSession = Depends(get_db),
):
    incident = await IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    _check_merchant_access(current_user, str(incident.merchant_id))
    incident = await IncidentService.resolve(db, incident, str(current_user.id), resolution_note)
    log_audit_event(
        db,
        event_type="incident.resolved",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"incident_id": incident_id},
    )
    await db.refresh(incident)
    await db.commit()
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/events", response_model=IncidentEventResponse, status_code=status.HTTP_201_CREATED)
async def add_incident_event(
    incident_id: str,
    payload: IncidentEventCreate,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    incident = await IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    _check_merchant_access(current_user, str(incident.merchant_id))
    event = await IncidentService.add_event(
        db,
        incident,
        event_type=payload.event_type,
        actor_user_id=str(current_user.id),
        message=payload.message,
        metadata_json=payload.metadata_json,
    )
    await db.commit()
    return IncidentEventResponse.model_validate(event)
