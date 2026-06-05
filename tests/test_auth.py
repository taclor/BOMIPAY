import inspect

import pytest

from bomipay.main import app, lifespan
from bomipay.services.security import create_refresh_token


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
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["email"] == registration["email"]
    assert payload["user"]["merchant_id"] is not None

    access = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert access.status_code == 200
    tokens = access.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["user"]["email"] == registration["email"]

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
    assert "email" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_me_requires_valid_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rejects_non_uuid_subject(client):
    token = create_refresh_token("not-a-uuid")
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token},
    )
    assert response.status_code == 401


def test_app_lifespan_and_cors_are_hardened():
    assert inspect.isasyncgenfunction(lifespan.__wrapped__)
    cors_middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors_middleware.kwargs["allow_origins"]
    assert "*" not in cors_middleware.kwargs["allow_origins"]


@pytest.mark.asyncio
async def test_register_auto_merchant_creation(client):
    """Registering without merchant_name creates a merchant from email prefix."""
    payload = {
        "full_name": "Emeka Obi",
        "email": "emeka.obi@example.com",
        "phone": "+2348000000099",
        "password": "SecureAutoMerch1!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["merchant_id"] is not None


@pytest.mark.asyncio
async def test_login_returns_user_object(client):
    """Login response must include user object with id, email, full_name, role, merchant_id."""
    payload = {
        "full_name": "Chioma Eze",
        "email": "chioma@example.com",
        "phone": "+2348000000098",
        "password": "LoginUserTest1!",
        "merchant_name": "Chioma Biz",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    data = login.json()
    assert "user" in data
    user = data["user"]
    assert user["email"] == payload["email"]
    assert user["full_name"] == payload["full_name"]
    assert user["role"] == "merchant_user"
    assert user["merchant_id"] is not None


@pytest.mark.asyncio
async def test_weak_password_returns_422(client):
    """Passwords that lack uppercase, lowercase, or digit must return 422."""
    base = {
        "full_name": "Weak Pass User",
        "email": "weakpass@example.com",
        "phone": "+2348000000097",
    }

    # too short
    r = await client.post("/api/v1/auth/register", json={**base, "password": "Short1!"})
    assert r.status_code == 422

    # no uppercase
    r = await client.post("/api/v1/auth/register", json={**base, "password": "alllowercasenum1234"})
    assert r.status_code == 422

    # no digit
    r = await client.post("/api/v1/auth/register", json={**base, "password": "NoDigitPasswordHere"})
    assert r.status_code == 422
