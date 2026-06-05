"""Tests for the Settlement model, service, and API routes."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from bomipay.models.merchant import Merchant, MerchantStatus
from bomipay.models.settlement import Settlement
from bomipay.services.settlement import (
    get_settlement_summary,
    list_settlements,
    upsert_settlement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_merchant(db: AsyncSession) -> Merchant:
    m = Merchant(
        id=uuid.uuid4(),
        name=f"Test Merchant {uuid.uuid4().hex[:8]}",
        email=f"test-{uuid.uuid4().hex[:6]}@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db.add(m)
    await db.flush()
    return m


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_settlement_creates_record(db_session: AsyncSession):
    merchant = await _make_merchant(db_session)
    s = await upsert_settlement(
        db=db_session,
        merchant_id=str(merchant.id),
        provider_name="paystack",
        reference="SETL-001",
        amount_minor=50000,
        currency="NGN",
        status="settled",
        settled_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert s.id is not None
    assert s.settlement_reference == "SETL-001"
    assert s.amount_minor == 50000
    assert s.status == "settled"


@pytest.mark.asyncio
async def test_upsert_settlement_idempotent(db_session: AsyncSession):
    """Calling upsert twice with the same reference must not create a duplicate."""
    merchant = await _make_merchant(db_session)
    await upsert_settlement(
        db=db_session,
        merchant_id=str(merchant.id),
        provider_name="paystack",
        reference="SETL-IDEM",
        amount_minor=10000,
        currency="NGN",
        status="pending",
    )
    updated = await upsert_settlement(
        db=db_session,
        merchant_id=str(merchant.id),
        provider_name="paystack",
        reference="SETL-IDEM",
        amount_minor=10000,
        currency="NGN",
        status="settled",
        settled_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )
    # Should have updated the existing record, not created a second one
    settlements = await list_settlements(db_session, merchant_id=str(merchant.id))
    assert len(settlements) == 1
    assert settlements[0].status == "settled"
    assert updated.id == settlements[0].id


@pytest.mark.asyncio
async def test_list_settlements_paginated(db_session: AsyncSession):
    merchant = await _make_merchant(db_session)
    for i in range(5):
        await upsert_settlement(
            db=db_session,
            merchant_id=str(merchant.id),
            provider_name="paystack",
            reference=f"SETL-PAGE-{i}",
            amount_minor=1000 * (i + 1),
            currency="NGN",
            status="settled",
        )

    page1 = await list_settlements(db_session, merchant_id=str(merchant.id), page=1, per_page=3)
    page2 = await list_settlements(db_session, merchant_id=str(merchant.id), page=2, per_page=3)
    assert len(page1) == 3
    assert len(page2) == 2
    # no overlap
    ids1 = {s.id for s in page1}
    ids2 = {s.id for s in page2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_settlement_summary_totals(db_session: AsyncSession):
    merchant = await _make_merchant(db_session)
    await upsert_settlement(
        db=db_session,
        merchant_id=str(merchant.id),
        provider_name="paystack",
        reference="SUMM-S1",
        amount_minor=100000,
        currency="NGN",
        status="settled",
    )
    await upsert_settlement(
        db=db_session,
        merchant_id=str(merchant.id),
        provider_name="paystack",
        reference="SUMM-P1",
        amount_minor=25000,
        currency="NGN",
        status="pending",
    )

    summary = await get_settlement_summary(db_session, merchant_id=str(merchant.id))
    assert summary["total_settled"] == 100000
    assert summary["total_pending"] == 25000
    assert len(summary["by_currency_status"]) == 2
