import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    registration = {
        "full_name": "Ada Nwosu",
        "email": "ada@example.com",
        "phone": "+2348000000001",
        "password": "SuperSecurePass123!",
        "merchant_name": "Ada Stores",
        "business_type": "retail",
        "country": "NG",
    }

    response = await client.post("/api/v1/auth/register", json=registration)
    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == registration["email"]
    assert payload["merchant_id"] is not None
    access = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert access.status_code == 200
    tokens = access.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=auth_header)
    assert me.status_code == 200
    assert me.json()["email"] == registration["email"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_duplicate_registration_is_conflict(client):
    payload = {
        "full_name": "Tunde Adebayo",
        "email": "tunde@example.com",
        "phone": "+2348000000002",
        "password": "AnotherSecurePass123!",
        "merchant_name": "Tunde Ventures",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_auth_me_requires_valid_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
