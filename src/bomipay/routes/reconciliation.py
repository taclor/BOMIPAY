from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.reconciliation import (
    ExpectedPaymentImportItem,
    ExpectedPaymentImportResponse,
    ExpectedPaymentResponse,
    ReconciliationResultResponse,
    ReconciliationRunCreateRequest,
    ReconciliationRunResponse,
    ReconciliationSummaryResponse,
)
from ..services.auth import get_current_active_user
from ..services.reconciliation import ReconciliationService

router = APIRouter()


def get_effective_merchant_id(current_user, merchant_id: str | None):
    if current_user.role == Role.admin:
        return merchant_id
    return str(current_user.merchant_id) if current_user.merchant_id is not None else None


@router.post("/reconciliation/expected-payments/import", response_model=ExpectedPaymentImportResponse)
@router.post("/reconciliation/import", response_model=ExpectedPaymentImportResponse)
async def import_expected_payments(
    request: Request,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ExpectedPaymentImportResponse:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    content_type = request.headers.get("content-type", "")
    validation_errors: list[str] = []
    expected_items: list[ExpectedPaymentImportItem] = []
    rows_received = 0
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file upload is required")
            expected_items, validation_errors = await ReconciliationService.parse_expected_payment_csv(file)
            rows_received = len(expected_items) + len(validation_errors)
        else:
            body = await request.json()
            payments = body.get("expected_payments")
            if payments is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expected_payments payload is required")
            expected_items, validation_errors = ReconciliationService.validate_expected_payments(payments)
            rows_received = len(payments)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid expected payments payload: {exc}")

    result = await ReconciliationService.import_expected_payments(
        db,
        effective_merchant_id,
        expected_items,
        rows_received=rows_received,
    )
    result["errors"].extend(validation_errors)
    return ExpectedPaymentImportResponse(**result)


@router.get("/reconciliation/expected-payments", response_model=list[ExpectedPaymentResponse])
async def list_expected_payments(
    merchant_id: str | None = Query(None),
    status: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExpectedPaymentResponse]:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    payments = await ReconciliationService.list_expected_payments(db, effective_merchant_id, status, from_date, to_date)
    return payments


@router.post("/reconciliation/runs", response_model=ReconciliationRunResponse)
async def create_reconciliation_run(
    body: ReconciliationRunCreateRequest,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationRunResponse:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if body.date_from >= body.date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

    run = await ReconciliationService.create_reconciliation_run(
        db, effective_merchant_id, body.date_from, body.date_to, body.run_name
    )
    try:
        await ReconciliationService.execute_reconciliation_run(db, run)
    except Exception as exc:
        from ..models.reconciliation import ReconciliationRunStatus

        run.status = ReconciliationRunStatus.failed
        await db.flush()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reconciliation run failed: {exc}")
    return run


@router.get("/reconciliation/runs", response_model=list[ReconciliationRunResponse])
async def list_reconciliation_runs(
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReconciliationRunResponse]:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")

    runs = await ReconciliationService.list_reconciliation_runs(db, effective_merchant_id)
    return runs


@router.get("/reconciliation/runs/{run_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation_run(
    run_id: str,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationRunResponse:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")

    run = await ReconciliationService.get_reconciliation_run(db, run_id, effective_merchant_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation run not found")
    return run


@router.get("/reconciliation/runs/{run_id}/results", response_model=list[ReconciliationResultResponse])
async def get_reconciliation_run_results(
    run_id: str,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReconciliationResultResponse]:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")

    run = await ReconciliationService.get_reconciliation_run(db, run_id, effective_merchant_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation run not found")

    results = await ReconciliationService.get_reconciliation_results(db, run_id)
    return results


@router.get("/reconciliation/runs/{run_id}/export", response_model=list[ReconciliationResultResponse])
async def export_reconciliation_run(
    run_id: str,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReconciliationResultResponse]:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")

    run = await ReconciliationService.get_reconciliation_run(db, run_id, effective_merchant_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation run not found")

    results = await ReconciliationService.get_reconciliation_results(db, run_id)
    return results


@router.get("/reconciliation/runs/{run_id}/summary", response_model=ReconciliationSummaryResponse)
async def get_reconciliation_run_summary(
    run_id: str,
    merchant_id: str | None = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationSummaryResponse:
    effective_merchant_id = get_effective_merchant_id(current_user, merchant_id)
    if current_user.role != Role.admin and effective_merchant_id != str(current_user.merchant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if effective_merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="merchant_id is required")

    try:
        summary = await ReconciliationService.get_run_summary(db, run_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation run not found")
    if str(summary["merchant_id"]) != effective_merchant_id and current_user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return ReconciliationSummaryResponse(**summary)
