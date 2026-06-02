"""Tests for Data Source Management module."""
import pytest


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "DS User",
            "email": email,
            "phone": phone,
            "password": "DataSrcPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DataSrcPass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


_DS_PAYLOAD = {
    "source_type": "provider_api",
    "display_name": "Paystack API Source",
    "provider_name": "Paystack",
    "configuration_json": {"base_url": "https://api.paystack.co"},
}


@pytest.mark.asyncio
async def test_create_and_list_data_source(client):
    mid, headers = await _register_and_login(
        client, "ds_create@example.com", "+2348002000001"
    )
    payload = {**_DS_PAYLOAD, "merchant_id": mid}
    resp = await client.post("/api/v1/data-sources", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Paystack API Source"
    assert data["source_type"] == "provider_api"
    assert data["status"] == "pending_setup"
    assert data["merchant_id"] == mid

    list_resp = await client.get(
        f"/api/v1/data-sources?merchant_id={mid}", headers=headers
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == data["id"] for item in items)


@pytest.mark.asyncio
async def test_get_data_source_by_id(client):
    mid, headers = await _register_and_login(
        client, "ds_get@example.com", "+2348002000002"
    )
    payload = {**_DS_PAYLOAD, "merchant_id": mid}
    create = await client.post("/api/v1/data-sources", json=payload, headers=headers)
    ds_id = create.json()["id"]

    resp = await client.get(f"/api/v1/data-sources/{ds_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == ds_id


@pytest.mark.asyncio
async def test_update_data_source(client):
    mid, headers = await _register_and_login(
        client, "ds_update@example.com", "+2348002000003"
    )
    payload = {**_DS_PAYLOAD, "merchant_id": mid}
    create = await client.post("/api/v1/data-sources", json=payload, headers=headers)
    ds_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/data-sources/{ds_id}",
        json={"display_name": "Updated DS"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated DS"


@pytest.mark.asyncio
async def test_data_source_test_endpoint(client):
    mid, headers = await _register_and_login(
        client, "ds_test@example.com", "+2348002000004"
    )
    payload = {**_DS_PAYLOAD, "merchant_id": mid}
    create = await client.post("/api/v1/data-sources", json=payload, headers=headers)
    ds_id = create.json()["id"]

    resp = await client.post(
        f"/api/v1/data-sources/{ds_id}/test", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_data_source_sync_status(client):
    mid, headers = await _register_and_login(
        client, "ds_syncstatus@example.com", "+2348002000005"
    )
    payload = {**_DS_PAYLOAD, "merchant_id": mid}
    create = await client.post("/api/v1/data-sources", json=payload, headers=headers)
    ds_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/data-sources/{ds_id}/sync-status", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_data_source_tenant_isolation(client):
    mid_a, headers_a = await _register_and_login(
        client, "ds_tenant_a@example.com", "+2348002000006", "DS Tenant A"
    )
    mid_b, headers_b = await _register_and_login(
        client, "ds_tenant_b@example.com", "+2348002000007", "DS Tenant B"
    )

    payload = {**_DS_PAYLOAD, "merchant_id": mid_a}
    create = await client.post("/api/v1/data-sources", json=payload, headers=headers_a)
    ds_id = create.json()["id"]

    resp = await client.get(f"/api/v1/data-sources/{ds_id}", headers=headers_b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_data_source_requires_auth(client):
    resp = await client.get("/api/v1/data-sources")
    assert resp.status_code == 401
