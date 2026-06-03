import pytest

from bomipay.services.security import create_access_token, create_refresh_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTER = {"n": 10}  # offset to avoid collision with test_auth.py phones


def _unique_user(n: int) -> dict:
    return {
        "full_name": "Extended User",
        "email": f"extauth{n:03d}@example.com",
        "phone": f"+234800100{n:04d}",
        "password": "SecurePass123!",
        "merchant_name": f"ExtMerchant{n:03d}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    user = _unique_user(1)
    reg = await client.post("/api/v1/auth/register", json=user)
    assert reg.status_code == 201

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody-at-all@example.com", "password": "IrrelevantPass1!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_missing_required_fields(client):
    """Registering without required fields should return 422."""
    resp = await client.post("/api/v1/auth/register", json={"full_name": "No Email User"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_token_refresh_returns_new_access_token(client):
    user = _unique_user(4)
    reg = await client.post("/api/v1/auth/register", json=user)
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert login.status_code == 200
    tokens = login.json()
    original_access = tokens["access_token"]
    refresh_tok = tokens["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert resp.status_code == 200
    refreshed = resp.json()
    assert "access_token" in refreshed
    assert refreshed["access_token"] != original_access


@pytest.mark.asyncio
async def test_token_refresh_rejects_access_token_as_refresh(client):
    """Using an access token in the refresh endpoint must return 401."""
    user = _unique_user(5)
    reg = await client.post("/api/v1/auth/register", json=user)
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    access_token = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh_invalid_token(client):
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "totally.invalid.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_tampered_token(client):
    """A tampered bearer token must be rejected with 401."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.bad.sig"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
