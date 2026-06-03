import pytest


@pytest.mark.asyncio
async def test_provider_connect_and_list_for_merchant(client):
    registration = {
        "full_name": "Chidi Okafor",
        "email": "chidi@example.com",
        "phone": "+2348000000006",
        "password": "ProviderSecurePass123!",
        "merchant_name": "Chidi Retail",
        "business_type": "retail",
        "country": "NG",
    }

    reg_resp = await client.post("/api/v1/auth/register", json=registration)
    assert reg_resp.status_code == 201
    merchant_id = reg_resp.json()["merchant_id"]

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    connect_resp = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {
                "api_key": "pk_test_123",
                "secret_key": "sk_test_123",
            },
        },
        headers=headers,
    )
    assert connect_resp.status_code == 200
    payload = connect_resp.json()
    assert payload["success"] is True
    assert payload["data"]["provider_name"] == "paystack"

    list_resp = await client.get(f"/api/v1/providers?merchant_id={merchant_id}", headers=headers)
    assert list_resp.status_code == 200
    providers = list_resp.json()
    assert len(providers) == 1
    assert providers[0]["provider_name"] == "paystack"

    health_resp = await client.get(f"/api/v1/providers/paystack/health?merchant_id={merchant_id}", headers=headers)
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health["provider_name"] == "paystack"
    assert health["connected"] is True

    ds_resp = await client.get(f"/api/v1/data-sources?merchant_id={merchant_id}", headers=headers)
    assert ds_resp.status_code == 200
    provider_sources = [
        ds for ds in ds_resp.json()
        if ds["source_type"] == "provider_api" and ds.get("provider_account_id") == payload["data"]["provider_account_id"]
    ]
    assert len(provider_sources) == 1


@pytest.mark.asyncio
async def test_provider_connect_forbidden_for_other_merchant(client, db_session):
    # Create first merchant/user
    first_user_payload = {
        "full_name": "First Merchant",
        "email": "first@example.com",
        "phone": "+2348000000015",
        "password": "FirstPass123!",
        "merchant_name": "First Store",
        "business_type": "service",
        "country": "NG",
    }
    first_resp = await client.post("/api/v1/auth/register", json=first_user_payload)
    assert first_resp.status_code == 201
    first_merchant_id = first_resp.json()["merchant_id"]

    # Register second merchant/user
    second_user_payload = {
        "full_name": "Second Merchant",
        "email": "second@example.com",
        "phone": "+2348000000016",
        "password": "SecondPass123!",
        "merchant_name": "Second Store",
        "business_type": "service",
        "country": "NG",
    }
    second_resp = await client.post("/api/v1/auth/register", json=second_user_payload)
    assert second_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": second_user_payload["email"], "password": second_user_payload["password"]},
    )
    assert login_resp.status_code == 200
    second_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {second_token}"}

    connect_resp = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": first_merchant_id,
            "provider_name": "paystack",
            "credentials": {
                "api_key": "pk_test_321",
                "secret_key": "sk_test_321",
            },
        },
        headers=headers,
    )
    assert connect_resp.status_code == 403
