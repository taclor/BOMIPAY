import pytest

from bomipay.models.user import Role
from bomipay.services.security import create_access_token
from bomipay.services.user import UserService


@pytest.mark.asyncio
async def test_merchant_profile_and_provider_account_lifecycle(client):
    registration = {
        "full_name": "Mercy Okonkwo",
        "email": "mercy@example.com",
        "phone": "+2348000000003",
        "password": "StrongMerchantPass123!",
        "merchant_name": "Mercy Traders",
        "business_type": "wholesale",
        "country": "NG",
    }

    reg_resp = await client.post("/api/v1/auth/register", json=registration)
    assert reg_resp.status_code == 201
    user_payload = reg_resp.json()
    assert user_payload["user"]["email"] == registration["email"]

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}

    profile_resp = await client.get("/api/v1/merchant/me", headers=auth_header)
    assert profile_resp.status_code == 200
    profile = profile_resp.json()
    assert profile["name"] == registration["merchant_name"]
    assert profile["business_type"] == registration["business_type"]

    update_resp = await client.patch(
        "/api/v1/merchant/me",
        json={"business_type": "retail", "country": "NG"},
        headers=auth_header,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["business_type"] == "retail"

    create_account_resp = await client.post(
        "/api/v1/merchant/provider-accounts",
        json={
            "provider_name": "Paystack",
            "api_key": "sk_test_123",
            "secret": "secret_test_123",
        },
        headers=auth_header,
    )
    assert create_account_resp.status_code == 201
    account = create_account_resp.json()
    assert account["provider_name"] == "Paystack"
    assert account["merchant_id"] == profile["id"]

    list_resp = await client.get("/api/v1/merchant/provider-accounts", headers=auth_header)
    assert list_resp.status_code == 200
    accounts = list_resp.json()
    assert len(accounts) == 1
    assert accounts[0]["provider_name"] == "Paystack"


@pytest.mark.asyncio
async def test_admin_can_manage_merchants_and_members(client, db_session):
    admin = await UserService.create_user(
        db_session,
        email="admin@example.com",
        password="AdminSecurePass123!",
        full_name="System Admin",
        phone="+2348000000009",
        role=Role.admin,
    )
    await db_session.commit()

    access_token = create_access_token(str(admin.id))
    headers = {"Authorization": f"Bearer {access_token}"}

    merchant_payload = {
        "name": "Admin Merchant",
        "email": "admin-merchant@example.com",
        "phone": "+2348000000010",
        "business_type": "enterprise",
        "country": "NG",
    }

    create_resp = await client.post("/api/v1/merchants", json=merchant_payload, headers=headers)
    assert create_resp.status_code == 201
    merchant = create_resp.json()
    assert merchant["name"] == merchant_payload["name"]

    member_payload = {
        "full_name": "Merchant Member",
        "email": "member@example.com",
        "phone": "+2348000000011",
        "password": "MemberSecurePass123!",
        "role": "merchant_user",
    }

    member_resp = await client.post(
        f"/api/v1/merchants/{merchant['id']}/members",
        json=member_payload,
        headers=headers,
    )
    assert member_resp.status_code == 201
    member = member_resp.json()
    assert member["email"] == member_payload["email"]
    assert member["merchant_id"] == merchant["id"]

    list_resp = await client.get(f"/api/v1/merchants/{merchant['id']}/members", headers=headers)
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert any(item["email"] == member_payload["email"] for item in members)


@pytest.mark.asyncio
async def test_non_admin_cannot_create_merchant(client, db_session):
    merchant = await UserService.create_merchant_for_user(
        db_session,
        merchant_name="Existing Merchant",
        email="existing@example.com",
        phone="+2348000000012",
        business_type="services",
        country="NG",
    )
    user = await UserService.create_user(
        db_session,
        email="member2@example.com",
        password="MemberSecurePass456!",
        full_name="Existing Member",
        phone="+2348000000013",
        merchant_id=merchant.id,
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {access_token}"}

    create_resp = await client.post(
        "/api/v1/merchants",
        json={
            "name": "Forbidden Merchant",
            "email": "forbidden@example.com",
            "phone": "+2348000000014",
            "business_type": "retail",
            "country": "NG",
        },
        headers=headers,
    )
    assert create_resp.status_code == 403
