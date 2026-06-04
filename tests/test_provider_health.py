import uuid
from datetime import date, datetime, timedelta

import pytest

from bomipay.main import app
from bomipay.models.provider_health import HealthStatus, ProviderHealthMetrics
from bomipay.models.transaction import Transaction, TransactionStatus
from bomipay.models.transaction_event import TransactionEvent
from bomipay.models.reconciliation import Settlement
from bomipay.models.user import Role
from bomipay.services.auth import get_current_active_user
from bomipay.services.provider_health import ProviderHealthService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyUser:
    def __init__(self, role: Role, merchant_id: str):
        self.role = role
        self.merchant_id = merchant_id


def _merchant_dummy() -> DummyUser:
    return DummyUser(Role.merchant_user, str(uuid.uuid4()))


def _make_transaction(
    merchant_id: str, provider_name: str = "paystack", status: str = "success", **kwargs
) -> Transaction:
    defaults = dict(
        provider_transaction_id=str(uuid.uuid4()),
        internal_reference=str(uuid.uuid4()),
        external_reference=str(uuid.uuid4()),
        currency="NGN",
        amount=5000,
        status=status,
    )
    defaults.update(kwargs)
    return Transaction(merchant_id=merchant_id, provider_name=provider_name, **defaults)


def _make_transaction_event(
    transaction_id: str, provider_name: str = "paystack", status: str = "success"
) -> TransactionEvent:
    return TransactionEvent(
        transaction_id=transaction_id,
        provider_name=provider_name,
        provider_event_id=str(uuid.uuid4()),
        event_type="payment_confirmed",
        provider_payload={"status": status},
        status=status,
    )


def _make_settlement(
    merchant_id: str, provider_name: str = "paystack", **kwargs
) -> Settlement:
    now = datetime.now()
    defaults = dict(
        settlement_reference=str(uuid.uuid4()),
        amount=50000,
        currency="NGN",
        settled_at=now + timedelta(hours=1),
        created_at=now,
    )
    defaults.update(kwargs)
    return Settlement(merchant_id=merchant_id, provider_name=provider_name, **defaults)


# ---------------------------------------------------------------------------
# Tests: Daily Metrics Calculation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_daily_metrics_empty_day(db_session):
    """Test daily metrics calculation for a day with no transactions."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    metric = await ProviderHealthService.calculate_daily_metrics(
        db_session, merchant_id, provider_name, date.today()
    )

    assert metric.transaction_count == 0
    assert metric.transaction_success_count == 0
    assert metric.settlement_count == 0
    assert metric.webhook_event_count == 0
    assert metric.health_status == HealthStatus.healthy.value


@pytest.mark.asyncio
async def test_calculate_daily_metrics_with_transactions(db_session):
    """Test daily metrics calculation with transaction data."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"
    today = date.today()

    # Create success transactions
    for _ in range(8):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)

    # Create failed transactions
    for _ in range(2):
        tx = _make_transaction(merchant_id, provider_name, "failed")
        db_session.add(tx)

    await db_session.commit()

    metric = await ProviderHealthService.calculate_daily_metrics(db_session, merchant_id, provider_name, today)

    assert metric.transaction_count == 10
    assert metric.transaction_success_count == 8
    assert metric.transaction_fail_count == 2


@pytest.mark.asyncio
async def test_calculate_daily_metrics_with_settlements(db_session):
    """Test daily metrics calculation with settlement data."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"
    today = date.today()

    # Create settlements
    for i in range(3):
        settlement = _make_settlement(merchant_id, provider_name)
        db_session.add(settlement)

    await db_session.commit()

    metric = await ProviderHealthService.calculate_daily_metrics(db_session, merchant_id, provider_name, today)

    assert metric.settlement_count == 3
    assert metric.settlement_success_count == 3


@pytest.mark.asyncio
async def test_calculate_daily_metrics_with_webhook_events(db_session):
    """Test daily metrics calculation with webhook event data."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"
    today = date.today()

    # Create transaction
    tx = _make_transaction(merchant_id, provider_name, "success")
    db_session.add(tx)
    await db_session.commit()

    # Create webhook events
    event1 = _make_transaction_event(tx.id, provider_name, "success")
    event2 = _make_transaction_event(tx.id, provider_name, "success")
    event3 = _make_transaction_event(tx.id, provider_name, "failed")
    db_session.add(event1)
    db_session.add(event2)
    db_session.add(event3)
    await db_session.commit()

    metric = await ProviderHealthService.calculate_daily_metrics(db_session, merchant_id, provider_name, today)

    assert metric.webhook_event_count == 3
    assert metric.webhook_success_count == 2
    assert metric.webhook_fail_count == 1


# ---------------------------------------------------------------------------
# Tests: Reliability Score (7-day rolling)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_reliability_score_100_percent(db_session):
    """Test reliability score calculation with 100% success rate."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create all successful transactions
    for _ in range(10):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)

    await db_session.commit()

    score = await ProviderHealthService.calculate_reliability_score(db_session, merchant_id, provider_name)

    assert score == 10000  # 100% = 10000 basis points


@pytest.mark.asyncio
async def test_calculate_reliability_score_50_percent(db_session):
    """Test reliability score calculation with 50% success rate."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create 50% successful and 50% failed transactions
    for _ in range(5):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)
    for _ in range(5):
        tx = _make_transaction(merchant_id, provider_name, "failed")
        db_session.add(tx)

    await db_session.commit()

    score = await ProviderHealthService.calculate_reliability_score(db_session, merchant_id, provider_name)

    assert score == 5000  # 50% = 5000 basis points


@pytest.mark.asyncio
async def test_calculate_reliability_score_empty(db_session):
    """Test reliability score calculation with no data."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    score = await ProviderHealthService.calculate_reliability_score(db_session, merchant_id, provider_name)

    assert score == 10000  # Default to perfect score


@pytest.mark.asyncio
async def test_calculate_reliability_score_7_day_window(db_session):
    """Test that reliability score only considers last 7 days."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create old transaction (before 7 days)
    old_tx = _make_transaction(
        merchant_id, provider_name, "failed", created_at=datetime.now() - timedelta(days=8)
    )
    db_session.add(old_tx)

    # Create recent transactions (within 7 days)
    for _ in range(10):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)

    await db_session.commit()

    score = await ProviderHealthService.calculate_reliability_score(db_session, merchant_id, provider_name)

    assert score == 10000  # Only recent 10 successes, old failure ignored


# ---------------------------------------------------------------------------
# Tests: Settlement Lag Score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_settlement_lag_score_fast(db_session):
    """Test settlement lag score with fast settlements (<1 hour)."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create fast settlement (30 minutes after creation)
    settlement = _make_settlement(
        merchant_id, provider_name, settled_at=datetime.now() + timedelta(minutes=30)
    )
    db_session.add(settlement)
    await db_session.commit()

    score = await ProviderHealthService.calculate_settlement_lag_score(db_session, merchant_id, provider_name)

    assert score == 10000  # Max score for <1 hour


@pytest.mark.asyncio
async def test_calculate_settlement_lag_score_slow(db_session):
    """Test settlement lag score with slow settlements (>24 hours)."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create slow settlement (created 2 days ago, settled now = 48 hour lag)
    now = datetime.now()
    settlement = _make_settlement(
        merchant_id,
        provider_name,
        created_at=now - timedelta(hours=48),
        settled_at=now,
    )
    db_session.add(settlement)
    await db_session.commit()

    score = await ProviderHealthService.calculate_settlement_lag_score(db_session, merchant_id, provider_name)

    assert score == 0  # Min score for >24 hours


@pytest.mark.asyncio
async def test_calculate_settlement_lag_score_empty(db_session):
    """Test settlement lag score with no settlements."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    score = await ProviderHealthService.calculate_settlement_lag_score(db_session, merchant_id, provider_name)

    assert score == 10000  # Default to perfect score


# ---------------------------------------------------------------------------
# Tests: Webhook Failure Score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_webhook_failure_score_no_failures(db_session):
    """Test webhook failure score with no failures."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create transaction
    tx = _make_transaction(merchant_id, provider_name, "success")
    db_session.add(tx)
    await db_session.commit()

    # Create successful webhook events
    for _ in range(10):
        event = _make_transaction_event(tx.id, provider_name, "success")
        db_session.add(event)

    await db_session.commit()

    score = await ProviderHealthService.calculate_webhook_failure_score(db_session, merchant_id, provider_name)

    assert score == 10000  # 0% failure = 100%


@pytest.mark.asyncio
async def test_calculate_webhook_failure_score_50_percent_failure(db_session):
    """Test webhook failure score with 50% failures."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create transaction
    tx = _make_transaction(merchant_id, provider_name, "success")
    db_session.add(tx)
    await db_session.commit()

    # Create 50% failed webhook events
    for _ in range(5):
        event = _make_transaction_event(tx.id, provider_name, "success")
        db_session.add(event)
    for _ in range(5):
        event = _make_transaction_event(tx.id, provider_name, "failed")
        db_session.add(event)

    await db_session.commit()

    score = await ProviderHealthService.calculate_webhook_failure_score(db_session, merchant_id, provider_name)

    assert score == 5000  # 50% success = 5000


@pytest.mark.asyncio
async def test_calculate_webhook_failure_score_empty(db_session):
    """Test webhook failure score with no webhook events."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    score = await ProviderHealthService.calculate_webhook_failure_score(db_session, merchant_id, provider_name)

    assert score == 10000  # Default to perfect score


# ---------------------------------------------------------------------------
# Tests: Outage Detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_outage_windows_no_outages(db_session):
    """Test outage detection with no outages."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create successful transactions
    for _ in range(10):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)

    await db_session.commit()

    outages = await ProviderHealthService.detect_outage_windows(db_session, merchant_id, provider_name)

    assert len(outages) == 0


@pytest.mark.asyncio
async def test_detect_outage_windows_with_outage(db_session):
    """Test outage detection with 1+ hour outage."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create failed transactions in consecutive hours
    now = datetime.now()
    for hour in range(2):  # 2 hours of failures
        for _ in range(2):
            tx = _make_transaction(
                merchant_id,
                provider_name,
                "failed",
                created_at=now - timedelta(hours=hour),
            )
            db_session.add(tx)

    await db_session.commit()

    outages = await ProviderHealthService.detect_outage_windows(db_session, merchant_id, provider_name)

    assert len(outages) >= 1


# ---------------------------------------------------------------------------
# Tests: Health Status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_health_status_healthy(db_session):
    """Test health status classification as healthy."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create transactions with >99% success rate
    for _ in range(199):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)
    for _ in range(1):
        tx = _make_transaction(merchant_id, provider_name, "failed")
        db_session.add(tx)

    # Create successful webhook events
    tx = _make_transaction(merchant_id, provider_name, "success")
    db_session.add(tx)
    await db_session.commit()

    for _ in range(5):
        event = _make_transaction_event(tx.id, provider_name, "success")
        db_session.add(event)

    await db_session.commit()

    status = await ProviderHealthService.get_health_status(db_session, merchant_id, provider_name, date.today())

    assert status == HealthStatus.healthy.value


@pytest.mark.asyncio
async def test_get_health_status_degraded(db_session):
    """Test health status classification as degraded."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create transactions with 95% success rate
    for _ in range(95):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)
    for _ in range(5):
        tx = _make_transaction(merchant_id, provider_name, "failed")
        db_session.add(tx)

    await db_session.commit()

    status = await ProviderHealthService.get_health_status(db_session, merchant_id, provider_name, date.today())

    assert status == HealthStatus.degraded.value


@pytest.mark.asyncio
async def test_get_health_status_critical(db_session):
    """Test health status classification as critical."""
    merchant_id = str(uuid.uuid4())
    provider_name = "paystack"

    # Create transactions with 85% success rate (< 90%)
    for _ in range(85):
        tx = _make_transaction(merchant_id, provider_name, "success")
        db_session.add(tx)
    for _ in range(15):
        tx = _make_transaction(merchant_id, provider_name, "failed")
        db_session.add(tx)

    await db_session.commit()

    status = await ProviderHealthService.get_health_status(db_session, merchant_id, provider_name, date.today())

    assert status == HealthStatus.critical.value


# ---------------------------------------------------------------------------
# Tests: API Routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_provider_health_summary_empty(client):
    """Test health summary endpoint with no data."""
    dummy = _merchant_dummy()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get("/api/v1/providers/health-metrics")
    assert resp.status_code == 200
    assert resp.json() == []

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_get_provider_health_summary_with_data(client, db_session):
    """Test health summary endpoint with metrics data."""
    merchant_id = str(uuid.uuid4())
    dummy = DummyUser(Role.merchant_user, merchant_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    # Create metrics
    metric = ProviderHealthMetrics(
        merchant_id=merchant_id,
        provider_name="paystack",
        metric_date=date.today(),
        transaction_count=100,
        transaction_success_count=95,
        reliability_score_bps=9500,
        health_status=HealthStatus.healthy.value,
    )
    db_session.add(metric)
    await db_session.commit()

    resp = await client.get("/api/v1/providers/health-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["provider_name"] == "paystack"
    assert data[0]["reliability_score_bps"] == 9500

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_get_provider_health_detail(client, db_session):
    """Test detailed provider health endpoint."""
    merchant_id = str(uuid.uuid4())
    dummy = DummyUser(Role.merchant_user, merchant_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    # Create metrics
    metric = ProviderHealthMetrics(
        merchant_id=merchant_id,
        provider_name="paystack",
        metric_date=date.today(),
        transaction_count=100,
        transaction_success_count=95,
        reliability_score_bps=9500,
        settlement_lag_score_bps=9000,
        webhook_failure_score_bps=9500,
        health_status=HealthStatus.healthy.value,
    )
    db_session.add(metric)
    await db_session.commit()

    resp = await client.get("/api/v1/providers/paystack/health-metrics")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["provider_name"] == "paystack"
    assert data["reliability_score_bps"] == 9500
    assert data["health_status"] == "healthy"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_get_provider_health_detail_not_found(client):
    """Test detailed provider health endpoint with no data."""
    dummy = _merchant_dummy()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get("/api/v1/providers/paystack/health-metrics")
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_get_provider_health_history(client, db_session):
    """Test health history endpoint."""
    merchant_id = str(uuid.uuid4())
    dummy = DummyUser(Role.merchant_user, merchant_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    # Create metrics for multiple days
    for i in range(3):
        metric = ProviderHealthMetrics(
            merchant_id=merchant_id,
            provider_name="paystack",
            metric_date=date.today() - timedelta(days=i),
            transaction_count=100,
            transaction_success_count=95,
            reliability_score_bps=9500,
            health_status=HealthStatus.healthy.value,
        )
        db_session.add(metric)

    await db_session.commit()

    resp = await client.get("/api/v1/providers/paystack/health-history?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # Should be in ascending order by date
    assert data[0]["metric_date"] <= data[1]["metric_date"]

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_get_provider_health_summary_tenant_isolation(client, db_session):
    """Test tenant isolation for health data."""
    merchant_a_id = str(uuid.uuid4())
    merchant_b_id = str(uuid.uuid4())

    # Create metrics for merchant B
    metric = ProviderHealthMetrics(
        merchant_id=merchant_b_id,
        provider_name="paystack",
        metric_date=date.today(),
        transaction_count=100,
        transaction_success_count=95,
        reliability_score_bps=9500,
        health_status=HealthStatus.healthy.value,
    )
    db_session.add(metric)
    await db_session.commit()

    # Access as merchant A
    dummy = DummyUser(Role.merchant_user, merchant_a_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get("/api/v1/providers/health-metrics")
    assert resp.status_code == 200
    assert resp.json() == []  # Should not see merchant B's data

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_calculate_provider_health_endpoint(client, db_session):
    """Test manual health calculation endpoint."""
    merchant_id = str(uuid.uuid4())
    dummy = DummyUser(Role.merchant_user, merchant_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    # Create transactions
    tx = _make_transaction(merchant_id, "paystack", "success")
    db_session.add(tx)
    await db_session.commit()

    resp = await client.post("/api/v1/providers/paystack/calculate-health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_name"] == "paystack"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_calculate_provider_health_endpoint_with_date(client, db_session):
    """Test manual health calculation with specific date."""
    merchant_id = str(uuid.uuid4())
    dummy = DummyUser(Role.merchant_user, merchant_id)
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.post(
        "/api/v1/providers/paystack/calculate-health?calc_date=2024-01-15"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric_date"] == "2024-01-15"

    app.dependency_overrides.pop(get_current_active_user, None)
