"""
pytest performance tests — measure latency of key Bomi Pay API endpoints
using ASGI TestClient (no running server required).

Run:
    pytest tests/test_performance_endpoints.py -v -m performance

These tests use the TestClient / AsyncClient backed by the FastAPI ASGI app
with an in-process SQLite database so they run in any CI environment.
"""

import asyncio
import os
import pathlib
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ---------------------------------------------------------------------------
# Environment setup — must happen before importing the app
# ---------------------------------------------------------------------------

os.environ.setdefault("SECRET_KEY", "perf-test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./perf_test.db")
os.environ.setdefault("JWT_REFRESH_TOKEN_EXPIRE_SECONDS", "604800")
os.environ.setdefault("PROVIDER_ENCRYPTION_KEY", "perf-test-encryption-key-123456789")
os.environ.setdefault("PAYSTACK_WEBHOOK_SECRET", "perf-test-paystack-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bomipay.db import Base, get_db
from bomipay.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///./perf_test.db"
_PERF_DB_FILE = pathlib.Path("perf_test.db")

_PERF_USER = {
    "full_name": "Perf Test User",
    "email": "perf_test@bomipay.example.com",
    "phone": "+2348099990001",
    "password": "PerfTest123!",
    "merchant_name": "Perf Test Merchant",
    "business_type": "retail",
    "country": "NG",
}

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def perf_engine():
    if _PERF_DB_FILE.exists():
        _PERF_DB_FILE.unlink()
    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    if _PERF_DB_FILE.exists():
        _PERF_DB_FILE.unlink()


@pytest.fixture(scope="module")
async def perf_db(perf_engine):
    session_factory = async_sessionmaker(
        perf_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="module")
async def perf_client(perf_db: AsyncSession):
    async def _override_db():
        yield perf_db

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module")
async def auth_data(perf_client: AsyncClient):
    """Register + login once per module; return headers and merchant_id."""
    reg = await perf_client.post("/api/v1/auth/register", json=_PERF_USER)
    if reg.status_code not in (201, 409):
        pytest.fail(f"Registration failed: {reg.status_code} {reg.text}")

    login = await perf_client.post(
        "/api/v1/auth/login",
        json={"email": _PERF_USER["email"], "password": _PERF_USER["password"]},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    body = login.json()
    token = body["access_token"]
    merchant_id = body.get("merchant_id") or reg.json().get("merchant_id", "")
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "merchant_id": str(merchant_id),
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestEndpointLatency:
    """Latency assertions for key Bomi Pay endpoints.

    All tests use the ASGI transport (no network overhead) so the measured
    latency is purely application-layer (request parsing, DB query, serialisation).
    """

    async def test_health_endpoint_under_50ms(self, perf_client: AsyncClient) -> None:
        """Health check must respond in < 50ms."""
        start = time.perf_counter()
        response = await perf_client.get("/api/v1/health")
        duration_ms = _ms(start)

        assert response.status_code == 200
        assert duration_ms < 50, (
            f"Health check took {duration_ms:.1f}ms (expected < 50ms)"
        )

    async def test_health_live_under_20ms(self, perf_client: AsyncClient) -> None:
        """Liveness probe must be ultra-fast (< 20ms)."""
        start = time.perf_counter()
        response = await perf_client.get("/api/v1/health/live")
        duration_ms = _ms(start)

        assert response.status_code == 200
        assert duration_ms < 20, (
            f"Liveness probe took {duration_ms:.1f}ms (expected < 20ms)"
        )

    async def test_dashboard_cold_query_under_2s(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Dashboard cold query must complete in < 2s."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            f"/api/v1/dashboard?merchant_id={merchant_id}",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 2000, (
            f"Dashboard took {duration_ms:.1f}ms (expected < 2000ms)"
        )

    async def test_incident_list_under_500ms(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Incident list must be returned in < 500ms."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            f"/api/v1/incidents?merchant_id={merchant_id}&limit=20",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 500, (
            f"Incident list took {duration_ms:.1f}ms (expected < 500ms)"
        )

    async def test_timeline_query_under_1s(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Payment timeline query must complete in < 1s."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            f"/api/v1/timeline/payments?merchant_id={merchant_id}&limit=20",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 1000, (
            f"Timeline query took {duration_ms:.1f}ms (expected < 1000ms)"
        )

    async def test_transaction_list_under_500ms(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Transaction list must be returned in < 500ms."""
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            "/api/v1/transactions",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 500, (
            f"Transaction list took {duration_ms:.1f}ms (expected < 500ms)"
        )

    async def test_dashboard_metrics_under_1s(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Dashboard metrics endpoint must respond in < 1s."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            f"/api/v1/dashboard/metrics?merchant_id={merchant_id}",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 1000, (
            f"Dashboard metrics took {duration_ms:.1f}ms (expected < 1000ms)"
        )

    async def test_concurrent_dashboard_requests(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """20 concurrent dashboard requests must all succeed within 5s."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        tasks = [
            perf_client.get(
                f"/api/v1/dashboard?merchant_id={merchant_id}",
                headers=headers,
            )
            for _ in range(20)
        ]

        start = time.perf_counter()
        responses = await asyncio.gather(*tasks)
        total_ms = _ms(start)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 20, (
            f"Only {success_count}/20 concurrent dashboard requests succeeded"
        )
        assert total_ms < 5000, (
            f"20 concurrent dashboard requests took {total_ms:.1f}ms (expected < 5000ms)"
        )

    async def test_concurrent_webhook_submissions(
        self, perf_client: AsyncClient
    ) -> None:
        """50 concurrent webhook POSTs must not cause 5xx errors."""
        import hashlib
        import hmac
        import json

        secret = os.environ["PAYSTACK_WEBHOOK_SECRET"]
        payloads = []
        for i in range(50):
            body = {
                "event": "charge.success",
                "data": {
                    "id": 900000 + i,
                    "reference": f"concurrent_wh_{i}",
                    "amount": 100_000,
                    "currency": "NGN",
                    "status": "success",
                    "channel": "card",
                    "gateway_response": "Approved",
                    "paid_at": "2024-01-15T10:30:00Z",
                    "transaction_date": "2024-01-15T10:30:00Z",
                    "customer": {"email": f"wh{i}@test.com", "phone": "+2348000000001"},
                    "metadata": {},
                },
            }
            raw = json.dumps(body).encode()
            sig = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
            payloads.append((raw, sig))

        tasks = [
            perf_client.post(
                "/webhooks/paystack",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Paystack-Signature": sig,
                },
            )
            for raw, sig in payloads
        ]

        responses = await asyncio.gather(*tasks)
        server_errors = [r for r in responses if r.status_code >= 500]
        assert len(server_errors) == 0, (
            f"{len(server_errors)}/50 concurrent webhook requests returned 5xx"
        )

    async def test_action_center_under_500ms(
        self, perf_client: AsyncClient, auth_data: dict
    ) -> None:
        """Action center endpoint must respond in < 500ms."""
        merchant_id = auth_data["merchant_id"]
        headers = auth_data["headers"]

        start = time.perf_counter()
        response = await perf_client.get(
            f"/api/v1/action-center?merchant_id={merchant_id}",
            headers=headers,
        )
        duration_ms = _ms(start)

        assert response.status_code == 200, f"Unexpected status: {response.text}"
        assert duration_ms < 500, (
            f"Action center took {duration_ms:.1f}ms (expected < 500ms)"
        )

    async def test_repeated_health_requests_stable_latency(
        self, perf_client: AsyncClient
    ) -> None:
        """10 sequential health checks must all be < 50ms (no warm-up effect)."""
        durations = []
        for _ in range(10):
            start = time.perf_counter()
            response = await perf_client.get("/api/v1/health")
            durations.append(_ms(start))
            assert response.status_code == 200

        p95 = sorted(durations)[int(len(durations) * 0.95)]
        assert p95 < 50, (
            f"Health check P95 = {p95:.1f}ms over 10 requests (expected < 50ms)"
        )
