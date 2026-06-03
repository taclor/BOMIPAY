"""Tests for the Unified Payment Timeline API."""
import pytest


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Timeline User",
            "email": email,
            "phone": phone,
            "password": "TimelinePass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201, reg.text
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TimelinePass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_payment_timeline_empty(client):
    """New merchant should have an empty timeline."""
    mid, headers = await _register_and_login(
        client, "tl_empty@example.com", "+2349001000001"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_payment_timeline_requires_auth(client):
    """Unauthenticated request must return 401."""
    resp = await client.get("/api/v1/timeline/payments")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_payment_timeline_tenant_isolation(client):
    """Merchant A cannot see Merchant B's timeline."""
    mid_a, headers_a = await _register_and_login(
        client, "tl_iso_a@example.com", "+2349001000002", "TL Iso A"
    )
    mid_b, _ = await _register_and_login(
        client, "tl_iso_b@example.com", "+2349001000003", "TL Iso B"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid_b},
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_payment_timeline_date_filters(client):
    """date_from / date_to params are accepted and return a list."""
    mid, headers = await _register_and_login(
        client, "tl_dates@example.com", "+2349001000004"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={
            "merchant_id": mid,
            "date_from": "2020-01-01T00:00:00",
            "date_to": "2030-12-31T23:59:59",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_payment_timeline_status_filter(client):
    """status param is accepted and returns a list."""
    mid, headers = await _register_and_login(
        client, "tl_status@example.com", "+2349001000005"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid, "status": "success"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    for event in resp.json():
        if event.get("event_type") == "transaction_created":
            assert event["metadata"]["status"] == "success"


@pytest.mark.asyncio
async def test_payment_timeline_provider_filter(client):
    """provider param is accepted and returns a list."""
    mid, headers = await _register_and_login(
        client, "tl_provider@example.com", "+2349001000006"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid, "provider": "paystack"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_timeline_summary_empty(client):
    """Summary for a new merchant returns zero counts."""
    mid, headers = await _register_and_login(
        client, "tl_sum_empty@example.com", "+2349001000007"
    )
    resp = await client.get(
        "/api/v1/timeline/summary",
        params={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    for value in data.values():
        assert value == 0, f"Expected 0, got {value} in {data}"


@pytest.mark.asyncio
async def test_timeline_summary_requires_auth(client):
    """Unauthenticated request to /timeline/summary must return 401."""
    resp = await client.get("/api/v1/timeline/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_timeline_summary_days_param(client):
    """days query param is accepted (default and custom)."""
    mid, headers = await _register_and_login(
        client, "tl_sum_days@example.com", "+2349001000008"
    )
    for days in (7, 30, 90, 365):
        resp = await client.get(
            "/api/v1/timeline/summary",
            params={"merchant_id": mid, "days": days},
            headers=headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


@pytest.mark.asyncio
async def test_transaction_lifecycle_not_found(client):
    """Non-existent transaction ID returns 404."""
    _, headers = await _register_and_login(
        client, "tl_txn_404@example.com", "+2349001000009"
    )
    fake_id = "00000000-0000-0000-0000-000000000099"
    resp = await client.get(
        f"/api/v1/timeline/transactions/{fake_id}/events",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transaction_lifecycle_requires_auth(client):
    """Unauthenticated request to transaction lifecycle returns 401."""
    fake_id = "00000000-0000-0000-0000-000000000098"
    resp = await client.get(f"/api/v1/timeline/transactions/{fake_id}/events")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_timeline_event_type_filter(client):
    """event_types query param filters the event list."""
    mid, headers = await _register_and_login(
        client, "tl_evtype@example.com", "+2349001000010"
    )
    # Filter to only transaction_created events
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid, "event_types": "transaction_created"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for event in data:
        assert event["event_type"] == "transaction_created"

    # Filter to a type with no data — should still return empty list
    resp2 = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid, "event_types": "settlement_received"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)


@pytest.mark.asyncio
async def test_timeline_event_schema_keys(client):
    """Every event in the timeline has the required schema keys."""
    mid, headers = await _register_and_login(
        client, "tl_schema@example.com", "+2349001000011"
    )
    resp = await client.get(
        "/api/v1/timeline/payments",
        params={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 200
    required_keys = {"event_type", "timestamp", "entity_type", "entity_id", "summary"}
    for event in resp.json():
        missing = required_keys - set(event.keys())
        assert not missing, f"Event missing keys {missing}: {event}"
