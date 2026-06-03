"""Tests for Analytics: money-at-risk, dashboard, timeline, action center."""
import pytest
from datetime import datetime, timezone


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Analytics User",
            "email": email,
            "phone": phone,
            "password": "AnalyticsPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AnalyticsPass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Money-at-risk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_money_at_risk_returns_valid_structure(client):
    mid, headers = await _register_and_login(
        client, "analytics_mar@example.com", "+2348005000001"
    )
    resp = await client.get(
        f"/api/v1/analytics/money-at-risk?merchant_id={mid}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    # Required top-level integer fields — must exist and be non-negative integers
    for field in (
        "total_money_at_risk_minor",
        "failed_payments_amount_minor",
        "hanging_payments_amount_minor",
        "unsettled_successful_payments_amount_minor",
        "settlement_mismatch_amount_minor",
        "duplicate_payment_risk_amount_minor",
        "unresolved_dispute_amount_minor",
        "affected_transaction_count",
    ):
        assert field in data, f"Missing field: {field}"
        assert isinstance(data[field], int), f"{field} must be int (no floats)"
        assert data[field] >= 0, f"{field} must be non-negative"

    assert "top_providers_by_risk" in data
    assert "top_incidents" in data
    assert "recommended_actions" in data


@pytest.mark.asyncio
async def test_money_at_risk_tenant_isolation(client):
    _, headers_a = await _register_and_login(
        client, "analytics_mar_a@example.com", "+2348005000002", "Analytics A"
    )
    mid_b, _ = await _register_and_login(
        client, "analytics_mar_b@example.com", "+2348005000003", "Analytics B"
    )
    # Merchant A trying to read Merchant B's risk data
    resp = await client.get(
        f"/api/v1/analytics/money-at-risk?merchant_id={mid_b}", headers=headers_a
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_money_at_risk_requires_auth(client):
    resp = await client.get("/api/v1/analytics/money-at-risk")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Mission Control Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_mission_control_structure(client):
    mid, headers = await _register_and_login(
        client, "analytics_dash@example.com", "+2348005000004"
    )
    resp = await client.get(
        f"/api/v1/dashboard/mission-control?merchant_id={mid}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {
        "payment_success_rate",
        "failed_transaction_count",
        "money_at_risk_minor",
        "pending_settlements_count",
        "open_incidents_count",
        "provider_health_summary",
        "reconciliation_status",
        "ai_insight_summary",
    }
    for key in expected_keys:
        assert key in data, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_dashboard_tenant_isolation(client):
    _, headers_a = await _register_and_login(
        client, "analytics_dash_a@example.com", "+2348005000005", "Dash A"
    )
    mid_b, _ = await _register_and_login(
        client, "analytics_dash_b@example.com", "+2348005000006", "Dash B"
    )
    resp = await client.get(
        f"/api/v1/dashboard/mission-control?merchant_id={mid_b}", headers=headers_a
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Unified Payment Timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeline_returns_list(client):
    mid, headers = await _register_and_login(
        client, "analytics_timeline@example.com", "+2348005000007"
    )
    resp = await client.get(
        f"/api/v1/timeline/payments?merchant_id={mid}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_timeline_tenant_isolation(client):
    _, headers_a = await _register_and_login(
        client, "analytics_tl_a@example.com", "+2348005000008", "TL A"
    )
    mid_b, _ = await _register_and_login(
        client, "analytics_tl_b@example.com", "+2348005000009", "TL B"
    )
    resp = await client.get(
        f"/api/v1/timeline/payments?merchant_id={mid_b}", headers=headers_a
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Action Center
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_center_returns_list(client):
    mid, headers = await _register_and_login(
        client, "analytics_ac@example.com", "+2348005000010"
    )
    resp = await client.get(
        f"/api/v1/action-center?merchant_id={mid}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert isinstance(data["actions"], list)


@pytest.mark.asyncio
async def test_action_center_tenant_isolation(client):
    _, headers_a = await _register_and_login(
        client, "analytics_ac_a@example.com", "+2348005000011", "AC A"
    )
    mid_b, _ = await _register_and_login(
        client, "analytics_ac_b@example.com", "+2348005000012", "AC B"
    )
    resp = await client.get(
        f"/api/v1/action-center?merchant_id={mid_b}", headers=headers_a
    )
    assert resp.status_code == 403
