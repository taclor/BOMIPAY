"""Tests for Bank Account Management module."""
import pytest

from bomipay.models.user import Role
from bomipay.services.security import create_access_token
from bomipay.services.user import UserService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "BA User",
            "email": email,
            "phone": phone,
            "password": "BankAccPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BankAccPass123!"},
    )
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return merchant_id, headers


_BA_PAYLOAD = {
    "bank_name": "Access Bank",
    "bank_code": "044",
    "account_number": "0123456789",
    "account_name": "Test Merchant Ltd",
    "currency": "NGN",
    "purpose": "settlement",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_bank_account(client):
    merchant_id, headers = await _register_and_login(
        client, "ba_create@example.com", "+2348001000001"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}

    resp = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["bank_name"] == "Access Bank"
    assert data["merchant_id"] == merchant_id
    # account number must be masked
    assert "0123456789" not in data["account_number_masked"]
    assert data["account_number_masked"].endswith("6789")
    assert data["verification_status"] == "unverified"
    assert data["status"] == "active"

    # list
    list_resp = await client.get(
        f"/api/v1/bank-accounts?merchant_id={merchant_id}", headers=headers
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == data["id"]


@pytest.mark.asyncio
async def test_get_bank_account_by_id(client):
    merchant_id, headers = await _register_and_login(
        client, "ba_get@example.com", "+2348001000002"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}
    create = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    account_id = create.json()["id"]

    resp = await client.get(f"/api/v1/bank-accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == account_id


@pytest.mark.asyncio
async def test_update_bank_account(client):
    merchant_id, headers = await _register_and_login(
        client, "ba_update@example.com", "+2348001000003"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}
    create = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    account_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/bank-accounts/{account_id}",
        json={"account_name": "Updated Name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["account_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_bank_account(client):
    merchant_id, headers = await _register_and_login(
        client, "ba_delete@example.com", "+2348001000004"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}
    create = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    account_id = create.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/bank-accounts/{account_id}", headers=headers
    )
    assert del_resp.status_code == 204

    # deleted account should still be fetchable (soft delete) but archived
    get_resp = await client.get(
        f"/api/v1/bank-accounts/{account_id}", headers=headers
    )
    # soft delete returns the account with archived status or 404 — either is acceptable
    assert get_resp.status_code in (200, 404)
    if get_resp.status_code == 200:
        assert get_resp.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_verify_bank_account(client):
    merchant_id, headers = await _register_and_login(
        client, "ba_verify@example.com", "+2348001000005"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}
    create = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    account_id = create.json()["id"]

    resp = await client.post(
        f"/api/v1/bank-accounts/{account_id}/verify", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bank_account_id"] == account_id
    assert data["verification_status"] == "verified"


@pytest.mark.asyncio
async def test_bank_account_tenant_isolation(client):
    """Merchant A cannot read merchant B's bank accounts."""
    mid_a, headers_a = await _register_and_login(
        client, "ba_tenant_a@example.com", "+2348001000006", "Tenant A"
    )
    mid_b, headers_b = await _register_and_login(
        client, "ba_tenant_b@example.com", "+2348001000007", "Tenant B"
    )

    payload = {**_BA_PAYLOAD, "merchant_id": mid_a}
    create = await client.post("/api/v1/bank-accounts", json=payload, headers=headers_a)
    account_id = create.json()["id"]

    # Merchant B tries to access merchant A's account
    resp = await client.get(
        f"/api/v1/bank-accounts/{account_id}", headers=headers_b
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bank_account_requires_auth(client):
    resp = await client.get("/api/v1/bank-accounts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bank_account_account_number_never_in_plain(client):
    """Plain account number must never appear in the response."""
    merchant_id, headers = await _register_and_login(
        client, "ba_plain@example.com", "+2348001000008"
    )
    payload = {**_BA_PAYLOAD, "merchant_id": merchant_id}
    create_resp = await client.post("/api/v1/bank-accounts", json=payload, headers=headers)
    assert "0123456789" not in create_resp.text
