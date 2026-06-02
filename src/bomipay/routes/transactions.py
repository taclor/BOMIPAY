from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.transaction import Transaction
from ..schemas.transaction import TransactionResponse
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
