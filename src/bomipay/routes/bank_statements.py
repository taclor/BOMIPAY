import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.bank_statement import (
    BankStatementEntryResponse,
    BankStatementImportResponse,
)
from ..services.audit import log_audit_event
from ..services.auth import require_role
from ..services.bank_statement import BankStatementService

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Bank Statements"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance)


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.post(
    "/bank-statements/import",
    response_model=BankStatementImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_bank_statement(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = Form(None),
    bank_account_id: Optional[str] = Form(None),
    currency: str = Form("NGN"),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective_merchant_id = str(merchant_id or current_user.merchant_id or "")
    if not effective_merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective_merchant_id)

    file_name = file.filename or "upload.csv"
    file_ext = file_name.rsplit(".", 1)[-1].lower()
    if file_ext not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")

    content = await file.read()

    import_record = await BankStatementService.create_import(
        db,
        merchant_id=effective_merchant_id,
        file_name=file_name,
        file_type=file_ext,
        bank_account_id=bank_account_id,
    )

    if file_ext == "csv":
        import_record = await BankStatementService.process_csv_import(
            db, import_record, content, default_currency=currency
        )
    elif file_ext == "xlsx":
        import_record = await BankStatementService.process_xlsx_import(
            db, import_record, content, default_currency=currency
        )

    log_audit_event(
        db,
        event_type="bank_statement.imported",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={"import_id": str(import_record.id), "file_name": file_name},
    )
    await db.commit()
    return BankStatementImportResponse.model_validate(import_record)


@router.get("/bank-statements/imports", response_model=list[BankStatementImportResponse])
async def list_imports(
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    imports = await BankStatementService.list_imports(db, effective)
    return [BankStatementImportResponse.model_validate(i) for i in imports]


@router.get("/bank-statements/imports/{import_id}", response_model=BankStatementImportResponse)
async def get_import(
    import_id: str,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    imp = await BankStatementService.get_import(db, import_id)
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    _check_merchant_access(current_user, str(imp.merchant_id))
    return BankStatementImportResponse.model_validate(imp)


@router.get("/bank-statements/imports/{import_id}/entries", response_model=list[BankStatementEntryResponse])
async def list_import_entries(
    import_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    imp = await BankStatementService.get_import(db, import_id)
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    _check_merchant_access(current_user, str(imp.merchant_id))
    entries = await BankStatementService.list_entries_for_import(
        db, import_id, str(imp.merchant_id), skip=skip, limit=limit
    )
    return [BankStatementEntryResponse.model_validate(e) for e in entries]


@router.get("/bank-statements/entries", response_model=list[BankStatementEntryResponse])
async def list_entries(
    merchant_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    effective = str(merchant_id or current_user.merchant_id or "")
    if not effective:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, effective)
    entries = await BankStatementService.list_entries(
        db, effective, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return [BankStatementEntryResponse.model_validate(e) for e in entries]


@router.post("/bank-statements/imports/{import_id}/reconcile")
async def reconcile_import(
    import_id: str,
    merchant_id: Optional[str] = None,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    imp = await BankStatementService.get_import(db, import_id)
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    
    effective = str(merchant_id or current_user.merchant_id or "")
    _check_merchant_access(current_user, effective)
    
    if str(imp.merchant_id) != str(effective):
        raise HTTPException(status_code=403, detail="Merchant ID mismatch")
    
    try:
        result = await BankStatementService.reconcile_import(db, import_id, effective)
        
        log_audit_event(
            db,
            event_type="bank_statement.reconciled",
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
            event_payload={"import_id": import_id, "matched": result["matched"], "unmatched": result["unmatched"]},
        )
        
        return {
            "import_id": import_id,
            "matched": result["matched"],
            "unmatched": result["unmatched"],
            "total": result["total"],
        }
    except Exception as e:
        logger.error(f"Reconciliation error: {str(e)}", extra={"import_id": import_id})
        raise HTTPException(status_code=500, detail="Reconciliation failed")
