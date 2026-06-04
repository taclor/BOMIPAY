from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.ledger import LedgerAccount, JournalEntry, FeeRecord
from ..services.auth import get_current_active_user
from ..services.ledger import LedgerService, LedgerException, UnbalancedEntryException
from ..schemas.auth import UserResponse

router = APIRouter(prefix="/ledger", tags=["ledger"])


# ============================================================================
# Account Management
# ============================================================================

class AccountCreateRequest:
    account_code: str


class AccountResponse:
    id: UUID
    merchant_id: UUID
    account_code: str
    is_active: bool
    created_at: str
    updated_at: str


@router.post("/accounts", response_model=dict)
async def create_account(
    account_code: str = Query(...),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ledger account for merchant."""
    try:
        account = await LedgerService.get_or_create_account(
            db=db,
            merchant_id=current_user.merchant_id,
            account_code=account_code,
            is_active=True,
        )
        await db.commit()
        return {
            "id": str(account.id),
            "merchant_id": str(account.merchant_id),
            "account_code": account.account_code,
            "is_active": account.is_active,
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat(),
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/accounts", response_model=list[dict])
async def list_accounts(
    merchant_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List ledger accounts for merchant."""
    from sqlalchemy import select
    
    query = select(LedgerAccount).where(
        LedgerAccount.merchant_id == current_user.merchant_id
    )
    
    if merchant_id and merchant_id != str(current_user.merchant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other merchant's accounts",
        )
    
    result = await db.execute(query)
    accounts = result.scalars().all()
    
    return [
        {
            "id": str(acc.id),
            "merchant_id": str(acc.merchant_id),
            "account_code": acc.account_code,
            "is_active": acc.is_active,
            "created_at": acc.created_at.isoformat(),
            "updated_at": acc.updated_at.isoformat(),
        }
        for acc in accounts
    ]


@router.get("/accounts/{account_id}/balance", response_model=dict)
async def get_account_balance(
    account_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current balance for account."""
    from sqlalchemy import select
    
    # Verify account belongs to current merchant
    account_uuid = UUID(account_id)
    result = await db.execute(
        select(LedgerAccount).where(LedgerAccount.id == account_uuid)
    )
    account = result.scalars().first()
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    
    if account.merchant_id != current_user.merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other merchant's account",
        )
    
    balance = await LedgerService.get_account_balance(db=db, account_id=account_uuid)
    return balance


# ============================================================================
# Journal Entries (Finance/Admin Only)
# ============================================================================

class JournalLineInput:
    account_code: str
    amount_minor: int
    line_type: str  # DEBIT or CREDIT
    description: Optional[str] = None


class JournalEntryCreateRequest:
    description: str
    lines: list[dict]  # List of {"account_code": str, "amount_minor": int, "line_type": str, "description": str?}
    idempotency_key: Optional[str] = None
    transaction_id: Optional[str] = None


@router.post("/entries", response_model=dict)
async def post_journal_entry(
    request: dict,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Post a balanced journal entry. Admin/Finance only.
    
    Request body:
    {
        "account_id": "uuid",
        "description": "string",
        "lines": [
            {"account_code": "MAIN", "amount_minor": 1000, "line_type": "DEBIT"},
            {"account_code": "FEE", "amount_minor": 1000, "line_type": "CREDIT"}
        ],
        "idempotency_key": "optional-key",
        "transaction_id": "optional-uuid"
    }
    """
    # TODO: Check if user has finance/admin role
    
    try:
        account_id = UUID(request.get("account_id"))
        lines = request.get("lines", [])
        idempotency_key = request.get("idempotency_key")
        transaction_id = request.get("transaction_id")
        description = request.get("description", "")
        
        # Verify account belongs to current merchant
        from sqlalchemy import select
        result = await db.execute(
            select(LedgerAccount).where(LedgerAccount.id == account_id)
        )
        account = result.scalars().first()
        
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        
        if account.merchant_id != current_user.merchant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot post to other merchant's account",
            )
        
        # Parse transaction_id if provided
        transaction_uuid = None
        if transaction_id:
            transaction_uuid = UUID(transaction_id)
        
        # Post journal entry
        entry = await LedgerService.post_journal_entry(
            db=db,
            merchant_id=current_user.merchant_id,
            account_id=account_id,
            description=description,
            lines=lines,
            idempotency_key=idempotency_key,
            transaction_id=transaction_uuid,
        )
        
        await db.commit()
        
        return {
            "id": str(entry.id),
            "merchant_id": str(entry.merchant_id),
            "account_id": str(entry.account_id),
            "description": entry.description,
            "idempotency_key": entry.idempotency_key,
            "transaction_id": str(entry.transaction_id) if entry.transaction_id else None,
            "lines": [
                {
                    "id": str(line.id),
                    "account_code": line.account_code,
                    "amount_minor": line.amount_minor,
                    "line_type": line.line_type,
                    "description": line.description,
                }
                for line in entry.ledger_lines
            ],
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }
    
    except UnbalancedEntryException as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerException as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/entries", response_model=list[dict])
async def list_journal_entries(
    merchant_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries for merchant."""
    if merchant_id and merchant_id != str(current_user.merchant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other merchant's entries",
        )
    
    account_uuid = None
    if account_id:
        account_uuid = UUID(account_id)
    
    entries = await LedgerService.get_journal_entries(
        db=db,
        merchant_id=current_user.merchant_id,
        account_id=account_uuid,
    )
    
    return [
        {
            "id": str(entry.id),
            "merchant_id": str(entry.merchant_id),
            "account_id": str(entry.account_id),
            "description": entry.description,
            "idempotency_key": entry.idempotency_key,
            "transaction_id": str(entry.transaction_id) if entry.transaction_id else None,
            "lines": [
                {
                    "id": str(line.id),
                    "account_code": line.account_code,
                    "amount_minor": line.amount_minor,
                    "line_type": line.line_type,
                    "description": line.description,
                }
                for line in entry.ledger_lines
            ],
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }
        for entry in entries
    ]


# ============================================================================
# Fees
# ============================================================================

@router.get("/fees", response_model=list[dict])
async def list_fees(
    merchant_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all fee records for merchant."""
    if merchant_id and merchant_id != str(current_user.merchant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other merchant's fees",
        )
    
    fees = await LedgerService.get_fees(db=db, merchant_id=current_user.merchant_id)
    
    return [
        {
            "id": str(fee.id),
            "merchant_id": str(fee.merchant_id),
            "journal_entry_id": str(fee.journal_entry_id),
            "fee_type": fee.fee_type,
            "amount_minor": fee.amount_minor,
            "description": fee.description,
            "created_at": fee.created_at.isoformat(),
            "updated_at": fee.updated_at.isoformat(),
        }
        for fee in fees
    ]
