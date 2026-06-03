import hashlib
import hmac
import json

import pytest
from bomipay.models import TransactionEvent


@pytest.mark.asyncio
async def test_paystack_webhook_ingestion_and_idempotency(client, db_session):
    payload = {
        "event": "charge.success",
        "data": {
            "id": 123456,
            "reference": "REF123",
            "amount": 500000,
            "currency": "NGN",
            "status": "success",
            "channel": "card",
            "gateway_response": "Approved",
            "transaction_date": "2026-04-11T12:00:00",
            "customer": {
                "email": "customer@example.com",
                "phone": "+2348000000004",
                "first_name": "Customer",
                "last_name": "Example",
            },
            "metadata": {"merchant_id": None},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    secret = "test-paystack-secret"
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()

    response = await client.post(
        "/webhooks/paystack",
        content=body,
        headers={"X-Paystack-Signature": "invalid-signature", "Content-Type": "application/json"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid webhook signature or provider connection"

    registration = {
        "full_name": "Paystack Merchant",
        "email": "paystack@example.com",
        "phone": "+2348000000005",
        "password": "PaystackSecurePass123!",
        "merchant_name": "Paystack Merchant Ltd",
        "business_type": "payments",
        "country": "NG",
    }
    reg_response = await client.post("/api/v1/auth/register", json=registration)
    assert reg_response.status_code == 201
    merchant_id = reg_response.json()["merchant_id"]

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    connect_response = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {
                "api_key": "pk_test_example",
                "secret_key": secret,
            },
        },
        headers=headers,
    )
    assert connect_response.status_code == 200

    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()

    response = await client.post(
        "/webhooks/paystack",
        content=body,
        headers={"X-Paystack-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    response = await client.post(
        "/webhooks/paystack",
        content=body,
        headers={"X-Paystack-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    failed_payload = dict(payload)
    failed_payload["event"] = "charge.failed"
    failed_payload["data"] = dict(payload["data"])
    failed_payload["data"]["id"] = 123457
    failed_payload["data"]["status"] = "failed"
    failed_payload["data"]["gateway_response"] = "Declined"
    failed_body = json.dumps(failed_payload).encode("utf-8")
    failed_signature = hmac.new(secret.encode("utf-8"), failed_body, hashlib.sha512).hexdigest()

    response = await client.post(
        "/webhooks/paystack",
        content=failed_body,
        headers={"X-Paystack-Signature": failed_signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    transactions = await client.get("/api/v1/transactions", headers=headers)
    assert transactions.status_code == 200
    assert len(transactions.json()) >= 2

    alerts = await client.get("/api/v1/alerts", headers=headers)
    assert alerts.status_code == 200
    assert len(alerts.json()) == 1
    alert_id = alerts.json()[0]["id"]

    sources = await client.get(f"/api/v1/data-sources?merchant_id={merchant_id}", headers=headers)
    assert sources.status_code == 200
    assert any(s["source_type"] == "provider_webhook" and s["provider_name"] == "paystack" for s in sources.json())

    ack = await client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"status": "acknowledged"},
        headers=headers,
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    from sqlalchemy import select

    result = await db_session.execute(
        select(TransactionEvent).where(TransactionEvent.provider_event_id == "123456")
    )
    events = result.scalars().all()
    assert len(events) == 1
