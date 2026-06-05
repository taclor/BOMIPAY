from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.settlement import SettlementResponse, SettlementSummaryResponse
from ..services.auth import get_current_active_user
from ..services.settlement import get_settlement_summary, list_settlements
from ..models.settlement import Settlement
from sqlalchemy import select

router = APIRouter(tags=["settlements"])


@router.get("/settlements", response_model=list[SettlementResponse])
async def list_settlements_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[SettlementResponse]:
    """List settlements for the current merchant, newest first."""
    return await list_settlements(
        db,
        merchant_id=str(current_user.merchant_id),
        page=page,
        per_page=per_page,
    )


@router.get("/settlements/summary", response_model=SettlementSummaryResponse)
async def settlement_summary_route(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SettlementSummaryResponse:
    """Summary statistics: total settled, pending, broken down by currency."""
    data = await get_settlement_summary(db, merchant_id=str(current_user.merchant_id))
    return SettlementSummaryResponse(**data)


@router.get("/settlements/{settlement_id}", response_model=SettlementResponse)
async def get_settlement_route(
    settlement_id: UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SettlementResponse:
    """Fetch a single settlement by ID."""
    result = await db.execute(
        select(Settlement).where(
            Settlement.id == settlement_id,
            Settlement.merchant_id == current_user.merchant_id,
        )
    )
    settlement = result.scalar_one_or_none()
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settlement not found")
    return settlement
