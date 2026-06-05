"""Settlement service — upsert, list, and summarise provider settlements."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.settlement import Settlement


async def upsert_settlement(
    db: AsyncSession,
    merchant_id: str,
    provider_name: str,
    reference: str,
    amount_minor: int,
    currency: str,
    status: str,
    settled_at: Optional[datetime] = None,
    expected_arrival_at: Optional[datetime] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
    provider_account_id: Optional[str] = None,
) -> Settlement:
    """Create or update a settlement record, idempotent on (merchant_id, reference)."""
    result = await db.execute(
        select(Settlement).where(
            Settlement.merchant_id == merchant_id,
            Settlement.settlement_reference == reference,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.status = status
        existing.amount = amount_minor
        existing.amount_minor = amount_minor
        existing.currency = currency
        if settled_at is not None:
            existing.settled_at = settled_at
        if expected_arrival_at is not None:
            existing.expected_arrival_at = expected_arrival_at
        if raw_payload is not None:
            existing.raw_payload_json = raw_payload
        if provider_account_id is not None:
            existing.provider_account_id = provider_account_id
        return existing

    settlement = Settlement(
        id=uuid.uuid4(),
        merchant_id=merchant_id,
        provider_account_id=provider_account_id,
        provider_name=provider_name,
        settlement_reference=reference,
        amount=amount_minor,
        amount_minor=amount_minor,
        currency=currency,
        status=status,
        settled_at=settled_at,
        expected_arrival_at=expected_arrival_at,
        raw_payload_json=raw_payload,
    )
    db.add(settlement)
    await db.flush()
    return settlement


async def list_settlements(
    db: AsyncSession,
    merchant_id: str,
    page: int = 1,
    per_page: int = 50,
) -> List[Settlement]:
    """Paginated list of settlements for a merchant, newest first."""
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Settlement)
        .where(Settlement.merchant_id == merchant_id)
        .order_by(Settlement.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    return list(result.scalars().all())


async def get_settlement_summary(db: AsyncSession, merchant_id: str) -> Dict[str, Any]:
    """Return totals broken down by status and currency."""
    result = await db.execute(
        select(
            Settlement.currency,
            Settlement.status,
            func.sum(Settlement.amount_minor).label("total"),
            func.count(Settlement.id).label("count"),
        )
        .where(Settlement.merchant_id == merchant_id)
        .group_by(Settlement.currency, Settlement.status)
    )
    rows = result.fetchall()

    summary: Dict[str, Any] = {"by_currency_status": [], "total_settled": 0, "total_pending": 0}
    for row in rows:
        total_val = row.total or 0
        summary["by_currency_status"].append(
            {
                "currency": row.currency,
                "status": row.status,
                "total_amount_minor": total_val,
                "count": row.count,
            }
        )
        if row.status == "settled":
            summary["total_settled"] += total_val
        elif row.status == "pending":
            summary["total_pending"] += total_val

    return summary
