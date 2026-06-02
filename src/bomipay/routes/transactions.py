from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.transaction import Transaction
from ..models.transaction_event import TransactionEvent
from ..schemas.transaction import TransactionResponse, TransactionEventResponse
from ..services.auth import get_current_active_user

router = APIRouter()


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    status: Optional[str] = Query(None),
    provider_name: Optional[str] = Query(None),
    reference: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    query = select(Transaction).where(Transaction.merchant_id == current_user.merchant_id)
    if status:
        query = query.where(Transaction.status == status)
    if provider_name:
        query = query.where(Transaction.provider_name == provider_name)
    if reference:
        query = query.where(
            (Transaction.internal_reference == reference) |
            (Transaction.external_reference == reference) |
            (Transaction.provider_transaction_id == reference)
        )
    if from_date:
        query = query.where(Transaction.created_at >= from_date)
    if to_date:
        query = query.where(Transaction.created_at <= to_date)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/transactions/search", response_model=list[TransactionResponse])
async def search_transactions(
    reference: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    provider_name: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    """Search transactions by reference, status, provider, or date range."""
    query = select(Transaction).where(Transaction.merchant_id == current_user.merchant_id)
    if status:
        query = query.where(Transaction.status == status)
    if provider_name:
        query = query.where(Transaction.provider_name == provider_name)
    if reference:
        query = query.where(
            (Transaction.internal_reference == reference) |
            (Transaction.external_reference == reference) |
            (Transaction.provider_transaction_id == reference)
        )
    if from_date:
        query = query.where(Transaction.created_at >= from_date)
    if to_date:
        query = query.where(Transaction.created_at <= to_date)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """Get a specific transaction by ID."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .where(Transaction.merchant_id == current_user.merchant_id)
    )
    transaction = result.scalars().first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


@router.get("/transactions/{transaction_id}/events", response_model=list[TransactionEventResponse])
async def get_transaction_events(
    transaction_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionEventResponse]:
    """Get all events for a transaction."""
    # Verify transaction belongs to current user
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .where(Transaction.merchant_id == current_user.merchant_id)
    )
    transaction = result.scalars().first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    # Get events for this transaction
    events_result = await db.execute(
        select(TransactionEvent)
        .where(TransactionEvent.transaction_id == transaction_id)
        .order_by(TransactionEvent.created_at)
    )
    return events_result.scalars().all()
