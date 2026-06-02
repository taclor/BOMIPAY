import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.provider_sync import ProviderSyncJobResponse, ProviderSyncRequest
from ..services.audit import log_audit_event
from ..services.auth import require_role
from ..services.merchant import ProviderAccountService
from ..services.provider_sync import ProviderSyncService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Provider Sync"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


async def _get_provider_account_or_404(db, provider_account_id: str, current_user):
    account = await ProviderAccountService.get_provider_account_by_id(db, provider_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Provider account not found")
    _check_merchant_access(current_user, str(account.merchant_id))
    return account


def _sync_router(sync_type: str):
    async def _sync(
        provider_account_id: str,
        payload: ProviderSyncRequest = ProviderSyncRequest(),
        current_user=Depends(require_role(*ALLOWED_ROLES)),
        db: AsyncSession = Depends(get_db),
    ) -> ProviderSyncJobResponse:
        account = await _get_provider_account_or_404(db, provider_account_id, current_user)
        job = await ProviderSyncService.create_job(
            db,
            merchant_id=str(account.merchant_id),
            provider_account_id=provider_account_id,
            sync_type=sync_type,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
        log_audit_event(
            db,
            event_type=f"provider_sync.{sync_type}.triggered",
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
            event_payload={"job_id": str(job.id), "provider_account_id": provider_account_id},
        )
        # Run sync inline (in production this would be queued)
        job = await ProviderSyncService.run_job(db, job, account)
        await db.commit()
        return ProviderSyncJobResponse.model_validate(job)

    return _sync


@router.post(
    "/providers/{provider_account_id}/sync/transactions",
    response_model=ProviderSyncJobResponse,
)
async def sync_transactions(
    provider_account_id: str,
    payload: ProviderSyncRequest = ProviderSyncRequest(),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await _sync_router("transactions")(provider_account_id, payload, current_user, db)


@router.post(
    "/providers/{provider_account_id}/sync/settlements",
    response_model=ProviderSyncJobResponse,
)
async def sync_settlements(
    provider_account_id: str,
    payload: ProviderSyncRequest = ProviderSyncRequest(),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await _sync_router("settlements")(provider_account_id, payload, current_user, db)


@router.post(
    "/providers/{provider_account_id}/sync/transfers",
    response_model=ProviderSyncJobResponse,
)
async def sync_transfers(
    provider_account_id: str,
    payload: ProviderSyncRequest = ProviderSyncRequest(),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await _sync_router("transfers")(provider_account_id, payload, current_user, db)


@router.post(
    "/providers/{provider_account_id}/sync/refunds",
    response_model=ProviderSyncJobResponse,
)
async def sync_refunds(
    provider_account_id: str,
    payload: ProviderSyncRequest = ProviderSyncRequest(),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await _sync_router("refunds")(provider_account_id, payload, current_user, db)


@router.get(
    "/providers/{provider_account_id}/sync-jobs",
    response_model=list[ProviderSyncJobResponse],
)
async def list_sync_jobs(
    provider_account_id: str,
    limit: int = 50,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_provider_account_or_404(db, provider_account_id, current_user)
    jobs = await ProviderSyncService.list_jobs_for_provider_account(
        db, provider_account_id, str(account.merchant_id), limit=limit
    )
    return [ProviderSyncJobResponse.model_validate(j) for j in jobs]


@router.get("/provider-sync-jobs/{job_id}", response_model=ProviderSyncJobResponse)
async def get_sync_job(
    job_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    job = await ProviderSyncService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    _check_merchant_access(current_user, str(job.merchant_id))
    return ProviderSyncJobResponse.model_validate(job)
