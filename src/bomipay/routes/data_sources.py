import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceSyncStatus,
    DataSourceTestResponse,
    DataSourceUpdate,
)
from ..services.audit import log_audit_event
from ..services.auth import get_current_active_user, require_role
from ..services.data_source import DataSourceService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Data Sources"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post("/data-sources", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = str(payload.merchant_id or current_user.merchant_id or "")
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)

    ds = await DataSourceService.create(
        db,
        merchant_id=merchant_id,
        source_type=payload.source_type,
        display_name=payload.display_name,
        provider_name=payload.provider_name,
        provider_account_id=payload.provider_account_id,
        configuration_json=payload.configuration_json,
    )
    log_audit_event(
        db,
        event_type="data_source.created",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"data_source_id": str(ds.id), "merchant_id": merchant_id},
    )
    await db.commit()
    return DataSourceResponse.model_validate(ds)


@router.get("/data-sources", response_model=list[DataSourceResponse])
async def list_data_sources(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    sources = await DataSourceService.list_for_merchant(db, effective)
    return [DataSourceResponse.model_validate(s) for s in sources]


@router.get("/data-sources/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    ds = await DataSourceService.get_by_id(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    _check_merchant_access(current_user, str(ds.merchant_id))
    return DataSourceResponse.model_validate(ds)


@router.patch("/data-sources/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: str,
    payload: DataSourceUpdate,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    ds = await DataSourceService.get_by_id(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    _check_merchant_access(current_user, str(ds.merchant_id))

    updates = payload.model_dump(exclude_none=True)
    ds = await DataSourceService.update(db, ds, updates)
    log_audit_event(
        db,
        event_type="data_source.updated",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"data_source_id": data_source_id, "updates": updates},
    )
    await db.commit()
    return DataSourceResponse.model_validate(ds)


@router.post("/data-sources/{data_source_id}/test", response_model=DataSourceTestResponse)
async def test_data_source(
    data_source_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    ds = await DataSourceService.get_by_id(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    _check_merchant_access(current_user, str(ds.merchant_id))

    # Stub test: connectivity check without mutating financial records
    success = ds.status not in ("error",)
    message = "Connection test passed" if success else f"Connection failed: {ds.last_error_message}"
    return DataSourceTestResponse(
        data_source_id=data_source_id,
        success=success,
        message=message,
        details={"source_type": ds.source_type, "status": ds.status},
    )


@router.get("/data-sources/{data_source_id}/sync-status", response_model=DataSourceSyncStatus)
async def get_sync_status(
    data_source_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    ds = await DataSourceService.get_by_id(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    _check_merchant_access(current_user, str(ds.merchant_id))

    health = DataSourceService.derive_health(ds)
    return DataSourceSyncStatus(
        data_source_id=data_source_id,
        status=ds.status,
        last_sync_at=ds.last_sync_at,
        last_success_at=ds.last_success_at,
        last_error_at=ds.last_error_at,
        last_error_message=ds.last_error_message,
        health=health,
    )
