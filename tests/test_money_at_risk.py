"""Tests for Money-at-Risk (MAR) Analytics module."""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from bomipay.models.user import Role
from bomipay.models.transaction import Transaction, TransactionStatus
from bomipay.models.money_at_risk import MoneyAtRisk
from bomipay.services.security import create_access_token
from bomipay.services.user import UserService
from bomipay.services.money_at_risk import MoneyAtRiskService


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    """Register a merchant and return merchant_id and auth headers."""
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "MAR Test User",
            "email": email,
            "phone": phone,
            "password": "MarPassword123!",  # At least 12 characters
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "MarPassword123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


async def _finance_headers(db_session, email: str, phone: str, merchant_id) -> dict:
    """Create a finance-role user linked to merchant_id and return auth headers."""
    user = await UserService.create_user(
        db_session,
        email=email,
        password="MarPassword123!",
        full_name="Finance User",
        phone=phone,
        role=Role.finance,
        merchant_id=merchant_id,
    )
    await db_session.commit()
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _create_transaction(
    merchant_id: str,
    amount: int,
    status: str = "pending",
    created_at: datetime = None,
    provider_name: str = "paystack",
) -> Transaction:
    """Create a transaction for testing."""
    now = created_at or datetime.now(timezone.utc)
    # Ensure datetime is timezone-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    txn = Transaction(
        merchant_id=merchant_id,
        provider_name=provider_name,
        provider_transaction_id=f"test_{now.timestamp()}",
        currency="NGN",
        amount=amount,
        status=status,
        created_at=now,
    )
    return txn


@pytest.mark.asyncio
async def test_calculate_mar_for_merchant_pending_only(db_session):
    """Test MAR calculation with only pending transactions."""
    # Setup
    mid = "00000000-0000-0000-0000-000000000001"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=30)
    
    # Create pending transaction older than 30 minutes
    txn = _create_transaction(
        mid, 500000, "pending", created_at=cutoff - timedelta(minutes=1)
    )
    db_session.add(txn)
    await db_session.commit()
    
    # Calculate MAR
    result = await MoneyAtRiskService.calculate_mar_for_merchant(db_session, mid, as_of_date=now)
    
    # Verify
    assert result["pending_transactions_amount"] == 500000.0
    assert result["pending_transactions_count"] == 1
    assert result["unreconciled_amount"] == 0.0
    assert result["failed_transfers_amount"] == 0.0
    assert result["total_at_risk"] == 500000.0


@pytest.mark.asyncio
async def test_calculate_mar_multiple_categories(db_session):
    """Test MAR calculation with transactions in all three categories."""
    # Setup
    mid = "00000000-0000-0000-0000-000000000002"
    now = datetime.now(timezone.utc)
    
    # Pending: older than 30 minutes
    pending_cutoff = now - timedelta(minutes=30)
    pending_txn = _create_transaction(mid, 300000, "pending", created_at=pending_cutoff - timedelta(minutes=1))
    db_session.add(pending_txn)
    
    # Unreconciled: successful transaction older than 7 days
    unreconciled_cutoff = now - timedelta(days=7)
    unreconciled_txn = _create_transaction(mid, 200000, "success", created_at=unreconciled_cutoff - timedelta(days=1))
    db_session.add(unreconciled_txn)
    
    # Failed: transaction older than 1 day
    failed_cutoff = now - timedelta(days=1)
    failed_txn = _create_transaction(mid, 150000, "failed", created_at=failed_cutoff - timedelta(hours=1))
    db_session.add(failed_txn)
    
    await db_session.commit()
    
    # Calculate MAR
    result = await MoneyAtRiskService.calculate_mar_for_merchant(db_session, mid, as_of_date=now)
    
    # Verify
    assert result["pending_transactions_amount"] == 300000.0
    assert result["pending_transactions_count"] == 1
    assert result["unreconciled_amount"] == 200000.0
    assert result["unreconciled_transaction_count"] == 1
    assert result["failed_transfers_amount"] == 150000.0
    assert result["failed_transfers_count"] == 1
    assert result["total_at_risk"] == 650000.0


@pytest.mark.asyncio
async def test_mar_breakdown_by_provider(db_session):
    """Test MAR breakdown by provider."""
    mid = "00000000-0000-0000-0000-000000000003"
    now = datetime.now(timezone.utc)
    pending_cutoff = now - timedelta(minutes=30)
    
    # Create pending transactions from different providers
    for i, provider in enumerate(["paystack", "flutterwave", "paystack"]):
        amount = (i + 1) * 100000
        txn = _create_transaction(
            mid, amount, "pending", created_at=pending_cutoff - timedelta(minutes=1),
            provider_name=provider
        )
        db_session.add(txn)
    
    await db_session.commit()
    
    result = await MoneyAtRiskService.calculate_mar_for_merchant(db_session, mid, as_of_date=now)
    
    # Verify
    breakdown = result["breakdown_by_provider"]
    assert "paystack" in breakdown
    assert breakdown["paystack"]["amount"] == 400000.0  # 100000 + 300000
    assert breakdown["paystack"]["count"] == 2
    assert "flutterwave" in breakdown
    assert breakdown["flutterwave"]["amount"] == 200000.0
    assert breakdown["flutterwave"]["count"] == 1


@pytest.mark.asyncio
async def test_mar_risk_score_calculation(db_session):
    """Test risk score calculation."""
    mid = "00000000-0000-0000-0000-000000000004"
    now = datetime.now(timezone.utc)
    pending_cutoff = now - timedelta(minutes=30)
    
    # Create multiple pending transactions to increase risk score
    for i in range(5):
        txn = _create_transaction(
            mid, 200000, "pending",
            created_at=pending_cutoff - timedelta(hours=2)
        )
        db_session.add(txn)
    
    await db_session.commit()
    
    result = await MoneyAtRiskService.calculate_mar_for_merchant(db_session, mid, as_of_date=now)
    
    # Risk score should be > 0 with multiple pending transactions
    assert result["risk_score"] > 0
    assert result["risk_score"] <= 100


@pytest.mark.asyncio
async def test_identify_at_risk_transactions_pending_only(db_session):
    """Test identifying pending at-risk transactions."""
    mid = "00000000-0000-0000-0000-000000000005"
    now = datetime.now(timezone.utc)
    pending_cutoff = now - timedelta(minutes=30)
    
    # Create pending transaction older than 30 minutes
    txn = _create_transaction(
        mid, 500000, "pending", created_at=pending_cutoff - timedelta(minutes=1)
    )
    db_session.add(txn)
    
    # Create recent pending transaction (should not be included)
    recent_txn = _create_transaction(
        mid, 100000, "pending", created_at=now - timedelta(minutes=5)
    )
    db_session.add(recent_txn)
    
    await db_session.commit()
    
    result = await MoneyAtRiskService.identify_at_risk_transactions(
        db_session, mid, category="pending", limit=100
    )
    
    # Only the old pending transaction should be identified
    assert len(result) == 1
    assert result[0]["amount"] == 500000


@pytest.mark.asyncio
async def test_identify_at_risk_transactions_all_categories(db_session):
    """Test identifying all at-risk transactions across categories."""
    mid = "00000000-0000-0000-0000-000000000006"
    now = datetime.now(timezone.utc)
    
    # Create transactions in each category
    pending_txn = _create_transaction(
        mid, 300000, "pending",
        created_at=now - timedelta(minutes=35)
    )
    db_session.add(pending_txn)
    
    unreconciled_txn = _create_transaction(
        mid, 200000, "success",
        created_at=now - timedelta(days=8)
    )
    db_session.add(unreconciled_txn)
    
    failed_txn = _create_transaction(
        mid, 150000, "failed",
        created_at=now - timedelta(days=2)
    )
    db_session.add(failed_txn)
    
    await db_session.commit()
    
    result = await MoneyAtRiskService.identify_at_risk_transactions(
        db_session, mid, category=None, limit=100
    )
    
    # All three transactions should be identified
    assert len(result) == 3
    amounts = {t["amount"] for t in result}
    assert amounts == {300000, 200000, 150000}


@pytest.mark.asyncio
async def test_project_resolution_with_trend(db_session):
    """Test MAR resolution projection based on trend."""
    mid = "00000000-0000-0000-0000-000000000007"
    now = datetime.now(timezone.utc)
    
    # Create historical MAR records showing decreasing trend
    for day in range(7):
        period_date = (now - timedelta(days=7 - day)).date()
        mar = MoneyAtRisk(
            merchant_id=mid,
            period_date=period_date,
            pending_transactions_amount=Decimal(str(500000 - (day * 50000))),
            pending_transactions_count=5,
            unreconciled_amount=Decimal("0"),
            unreconciled_transaction_count=0,
            failed_transfers_amount=Decimal("0"),
            failed_transfers_count=0,
            total_at_risk=Decimal(str(500000 - (day * 50000))),
            risk_score=50,
        )
        db_session.add(mar)
    
    await db_session.commit()
    
    result = await MoneyAtRiskService.project_resolution(db_session, mid, days_ahead=30)
    
    # With decreasing trend, should have an estimated resolution date
    assert result["estimated_resolution_date"] is not None
    assert result["days_to_resolution"] is not None
    assert result["confidence"] in ["low", "medium", "high"]
    assert len(result["projection"]) > 0


@pytest.mark.asyncio
async def test_get_alerts_for_high_mar_amount_exceeded(db_session):
    """Test alert generation when MAR amount exceeds threshold."""
    mid = "00000000-0000-0000-0000-000000000008"
    now = datetime.now(timezone.utc)
    
    # Create high MAR by adding pending transactions
    pending_cutoff = now - timedelta(minutes=30)
    for i in range(15):  # 15 * 500000 = 7.5M, exceeds 1M threshold
        txn = _create_transaction(
            mid, 500000, "pending",
            created_at=pending_cutoff - timedelta(minutes=5)
        )
        db_session.add(txn)
    
    # Create MAR record
    mar = MoneyAtRisk(
        merchant_id=mid,
        period_date=now.date(),
        pending_transactions_amount=Decimal("7500000"),
        pending_transactions_count=15,
        unreconciled_amount=Decimal("0"),
        unreconciled_transaction_count=0,
        failed_transfers_amount=Decimal("0"),
        failed_transfers_count=0,
        total_at_risk=Decimal("7500000"),
        risk_score=75,
    )
    db_session.add(mar)
    await db_session.commit()
    
    # Get alerts
    alerts = await MoneyAtRiskService.get_alerts_for_high_mar(
        db_session, mid, mar_threshold=1000000.0, score_threshold=70
    )
    
    # Should have alerts
    assert len(alerts) > 0
    # Should have high amount alert
    amount_alerts = [a for a in alerts if a["type"] == "high_amount"]
    assert len(amount_alerts) > 0


@pytest.mark.asyncio
async def test_get_alerts_for_high_mar_score_exceeded(db_session):
    """Test alert generation when risk score exceeds threshold."""
    mid = "00000000-0000-0000-0000-000000000009"
    now = datetime.now(timezone.utc)
    
    # Create MAR record with high risk score
    mar = MoneyAtRisk(
        merchant_id=mid,
        period_date=now.date(),
        pending_transactions_amount=Decimal("500000"),
        pending_transactions_count=5,
        unreconciled_amount=Decimal("0"),
        unreconciled_transaction_count=0,
        failed_transfers_amount=Decimal("0"),
        failed_transfers_count=0,
        total_at_risk=Decimal("500000"),
        risk_score=80,  # Exceeds threshold of 70
    )
    db_session.add(mar)
    await db_session.commit()
    
    # Get alerts
    alerts = await MoneyAtRiskService.get_alerts_for_high_mar(
        db_session, mid, mar_threshold=10000000.0, score_threshold=70
    )
    
    # Should have risk score alert
    score_alerts = [a for a in alerts if a["type"] == "high_risk_score"]
    assert len(score_alerts) > 0


@pytest.mark.asyncio
async def test_get_alerts_for_high_mar_worsening_trend(db_session):
    """Test alert generation when MAR trend is worsening."""
    mid = "00000000-0000-0000-0000-000000000010"
    now = datetime.now(timezone.utc)
    
    # Create yesterday's MAR
    yesterday_mar = MoneyAtRisk(
        merchant_id=mid,
        period_date=(now - timedelta(days=1)).date(),
        pending_transactions_amount=Decimal("500000"),
        pending_transactions_count=5,
        unreconciled_amount=Decimal("0"),
        unreconciled_transaction_count=0,
        failed_transfers_amount=Decimal("0"),
        failed_transfers_count=0,
        total_at_risk=Decimal("500000"),
        risk_score=50,
    )
    db_session.add(yesterday_mar)
    
    # Create today's MAR with 20%+ increase
    today_mar = MoneyAtRisk(
        merchant_id=mid,
        period_date=now.date(),
        pending_transactions_amount=Decimal("700000"),  # 40% increase
        pending_transactions_count=7,
        unreconciled_amount=Decimal("0"),
        unreconciled_transaction_count=0,
        failed_transfers_amount=Decimal("0"),
        failed_transfers_count=0,
        total_at_risk=Decimal("700000"),
        risk_score=60,
    )
    db_session.add(today_mar)
    await db_session.commit()
    
    # Get alerts
    alerts = await MoneyAtRiskService.get_alerts_for_high_mar(
        db_session, mid, mar_threshold=10000000.0, score_threshold=70
    )
    
    # Should have worsening trend alert
    worsening_alerts = [a for a in alerts if a["type"] == "worsening_trend"]
    assert len(worsening_alerts) > 0


@pytest.mark.asyncio
async def test_mar_current_endpoint(client, db_session):
    """Test GET /money-at-risk/current endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_current@example.com", "+2348004000001"
    )
    
    # Get current MAR
    resp = await client.get(f"/api/v1/money-at-risk/current?merchant_id={mid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert "total_at_risk" in data
    assert "risk_score" in data


@pytest.mark.asyncio
async def test_mar_trend_endpoint(client, db_session):
    """Test GET /money-at-risk/trend endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_trend@example.com", "+2348004000002"
    )
    
    # Get MAR trend
    resp = await client.get(f"/api/v1/money-at-risk/trend?merchant_id={mid}&days=30", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert data["days"] == 30
    assert "trend" in data
    assert isinstance(data["trend"], list)


@pytest.mark.asyncio
async def test_mar_breakdown_endpoint(client, db_session):
    """Test GET /money-at-risk/breakdown endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_breakdown@example.com", "+2348004000003"
    )
    
    # Get MAR breakdown
    resp = await client.get(f"/api/v1/money-at-risk/breakdown?merchant_id={mid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert "by_provider" in data
    assert "by_status" in data


@pytest.mark.asyncio
async def test_mar_at_risk_transactions_endpoint(client, db_session):
    """Test GET /money-at-risk/at-risk-transactions endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_txns@example.com", "+2348004000004"
    )
    
    # Get at-risk transactions
    resp = await client.get(
        f"/api/v1/money-at-risk/at-risk-transactions?merchant_id={mid}&category=pending",
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert data["category"] == "pending"
    assert "transactions" in data


@pytest.mark.asyncio
async def test_mar_projection_endpoint(client, db_session):
    """Test GET /money-at-risk/projection endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_projection@example.com", "+2348004000005"
    )
    
    # Get projection
    resp = await client.get(
        f"/api/v1/money-at-risk/projection?merchant_id={mid}&days_ahead=30",
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert "estimated_resolution_date" in data
    assert "projection" in data


@pytest.mark.asyncio
async def test_mar_alerts_endpoint(client, db_session):
    """Test GET /money-at-risk/alerts endpoint."""
    mid, headers = await _register_and_login(
        client, "mar_alerts@example.com", "+2348004000006"
    )
    
    # Get alerts
    resp = await client.get(
        f"/api/v1/money-at-risk/alerts?merchant_id={mid}&threshold=1000000",
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant_id"] == mid
    assert "alerts" in data
    assert "has_alerts" in data
    assert "high_risk" in data


@pytest.mark.asyncio
async def test_mar_tenant_isolation(client, db_session):
    """Test that MAR endpoints enforce tenant isolation."""
    mid1, headers1 = await _register_and_login(
        client, "mar_tenant1@example.com", "+2348004000007"
    )
    mid2, headers2 = await _register_and_login(
        client, "mar_tenant2@example.com", "+2348004000008"
    )
    
    # User from mid1 should not access mid2's MAR
    resp = await client.get(f"/api/v1/money-at-risk/current?merchant_id={mid2}", headers=headers1)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mar_requires_authentication(client):
    """Test that MAR endpoints require authentication."""
    mid = "00000000-0000-0000-0000-000000000099"
    
    # No auth header
    resp = await client.get(f"/api/v1/money-at-risk/current?merchant_id={mid}")
    assert resp.status_code in (401, 403)
    
    resp = await client.get(f"/api/v1/money-at-risk/trend?merchant_id={mid}")
    assert resp.status_code in (401, 403)
