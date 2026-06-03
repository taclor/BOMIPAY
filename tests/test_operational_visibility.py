import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from bomipay.models import Alert, AlertSeverity, AlertType, Merchant, Transaction, TransactionStatus
from bomipay.models.notification import NotificationStatus
from bomipay.services.alert import AlertService
from bomipay.services.detection import HangingTransactionDetector
from bomipay.services.notification import NotificationService
from bomipay.services.transaction import TransactionService


@pytest.mark.asyncio
async def test_transaction_query_filters_and_detail(client):
    registration = {
        "full_name": "Visibility Merchant",
        "email": "visibility@example.com",
        "phone": "+2348000000010",
        "password": "VisibilityPass123!",
        "merchant_name": "Visibility Store",
        "business_type": "retail",
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
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect_response = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {"api_key": "pk_vis_test", "secret_key": "test-paystack-secret"},
        },
        headers=headers,
    )
    assert connect_response.status_code == 200

    secret = "test-paystack-secret"
    for event_id, status in [(1001, "success"), (1002, "failed")]:
        payload = {
            "event": status == "success" and "charge.success" or "charge.failed",
            "data": {
                "id": event_id,
                "reference": f"REF{event_id}",
                "amount": 1000,
                "currency": "NGN",
                "status": status,
                "channel": "card",
                "gateway_response": status == "success" and "Approved" or "Declined",
                "transaction_date": "2026-04-11T12:00:00",
                "customer": {
                    "email": "customer@example.com",
                    "phone": "+2348000000004",
                    "first_name": "Customer",
                    "last_name": "Example",
                },
                "metadata": {},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
        response = await client.post(
            "/webhooks/paystack",
            content=body,
            headers={"X-Paystack-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

    transactions_resp = await client.get("/api/v1/transactions?status=success", headers=headers)
    assert transactions_resp.status_code == 200
    assert len(transactions_resp.json()) == 1

    search_resp = await client.get(
        "/api/v1/transactions/search?reference=REF1001",
        headers=headers,
    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1

    transaction_id = search_resp.json()[0]["id"]
    detail_resp = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["provider_name"] == "paystack"

    events_resp = await client.get(f"/api/v1/transactions/{transaction_id}/events", headers=headers)
    assert events_resp.status_code == 200
    assert len(events_resp.json()) == 1


@pytest.mark.asyncio
async def test_alert_acknowledge_and_resolve(client):
    registration = {
        "full_name": "Alert User",
        "email": "alertuser@example.com",
        "phone": "+2348000000011",
        "password": "AlertPass123!",
        "merchant_name": "Alert Store",
        "business_type": "services",
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
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect_response = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {"api_key": "pk_alert_test", "secret_key": "test-paystack-secret"},
        },
        headers=headers,
    )
    assert connect_response.status_code == 200

    payload = {
        "event": "charge.failed",
        "data": {
            "id": 2001,
            "reference": "REF2001",
            "amount": 5000,
            "currency": "NGN",
            "status": "failed",
            "channel": "card",
            "gateway_response": "Declined",
            "transaction_date": "2026-04-11T12:00:00",
            "customer": {"email": "customer@example.com", "phone": "+2348000000005", "first_name": "Customer", "last_name": "Example"},
            "metadata": {},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-paystack-secret", body, hashlib.sha512).hexdigest()
    response = await client.post(
        "/webhooks/paystack",
        content=body,
        headers={"X-Paystack-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200

    alerts_resp = await client.get("/api/v1/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) >= 1
    alert_id = alerts[0]["id"]

    ack_resp = await client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"

    resolve_resp = await client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=headers)
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_alert_deduplication_prevents_duplicate_open_alerts(db_session):
    merchant = Merchant(
        name="Dedup Merchant",
        email="dedup@example.com",
        phone="+2348000000015",
        country="NG",
    )
    db_session.add(merchant)
    await db_session.flush()

    alert1 = await AlertService.create_alert(
        db_session,
        merchant_id=merchant.id,
        alert_type=AlertType.transaction_failure,
        severity=AlertSeverity.high,
        description="Duplicate alert test",
        transaction_id=None,
        source_event_id="SOURCE123",
        rule_code="rule.transaction_failure",
    )
    await db_session.commit()

    alert2 = await AlertService.create_alert(
        db_session,
        merchant_id=merchant.id,
        alert_type=AlertType.transaction_failure,
        severity=AlertSeverity.high,
        description="Duplicate alert test again",
        transaction_id=None,
        source_event_id="SOURCE123",
        rule_code="rule.transaction_failure",
    )
    await db_session.commit()

    assert str(alert1.id) == str(alert2.id)
    assert alert2.occurrence_count == 2

    alert1.status = "resolved"
    await db_session.flush()
    await db_session.commit()

    alert3 = await AlertService.create_alert(
        db_session,
        merchant_id=merchant.id,
        alert_type=AlertType.transaction_failure,
        severity=AlertSeverity.high,
        description="Duplicate after resolve",
        transaction_id=None,
        source_event_id="SOURCE123",
        rule_code="rule.transaction_failure",
    )
    await db_session.commit()

    assert str(alert3.id) != str(alert1.id)


@pytest.mark.asyncio
async def test_notification_retry_logic_is_safe(client, db_session, monkeypatch):
    registration = {
        "full_name": "Retry Merchant",
        "email": "retry@example.com",
        "phone": "+2348000000016",
        "password": "RetryPass123!",
        "merchant_name": "Retry Store",
        "business_type": "services",
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
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect_response = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {"api_key": "pk_spike_test", "secret_key": "test-paystack-secret"},
        },
        headers=headers,
    )
    assert connect_response.status_code == 200

    notification = await NotificationService.create_notification(
        db_session,
        merchant_id=merchant_id,
        channel="email",
        message="Retryable email",
        delivery_key="retry-email-1",
    )
    await db_session.commit()

    attempts = {"count": 0}

    def flaky_adapter(recipient_email: str, subject: str, body: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return {"provider": "console", "delivered": True, "message_id": "msg-123"}

    monkeypatch.setattr(NotificationService, "email_adapter", flaky_adapter)

    result = await NotificationService.attempt_delivery(db_session, notification.id, "notify@example.com")
    await db_session.commit()
    assert result is not None
    assert result.status == NotificationStatus.retry_scheduled.value
    assert result.retry_count == 1

    result.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()
    await db_session.commit()

    result = await NotificationService.attempt_delivery(db_session, notification.id, "notify@example.com")
    await db_session.commit()
    assert result is not None
    assert result.status == NotificationStatus.sent.value
    assert result.retry_count == 1

    second_attempt = await NotificationService.attempt_delivery(db_session, notification.id, "notify@example.com")
    assert second_attempt is None


@pytest.mark.asyncio
async def test_hanging_transaction_detection_creates_one_alert(db_session):
    merchant = Merchant(
        name="Hanging Merchant",
        email="hang@example.com",
        phone="+2348000000014",
        country="NG",
    )
    db_session.add(merchant)
    await db_session.flush()

    transaction = Transaction(
        merchant_id=merchant.id,
        provider_name="paystack",
        provider_transaction_id="HANGING123",
        currency="NGN",
        amount=25000,
        status=TransactionStatus.pending.value,
        initiated_at=datetime.now(timezone.utc) - timedelta(minutes=45),
    )
    db_session.add(transaction)
    await db_session.flush()

    await HangingTransactionDetector.evaluate_transaction(db_session, transaction)
    await db_session.commit()

    result = await db_session.execute(
        select(func.count(Alert.id)).where(
            Alert.merchant_id == merchant.id,
            Alert.alert_type == "hanging_payment",
        )
    )
    count = result.scalar_one()
    assert count == 1

    await HangingTransactionDetector.evaluate_transaction(db_session, transaction)
    await db_session.commit()
    result = await db_session.execute(
        select(func.count(Alert.id)).where(
            Alert.merchant_id == merchant.id,
            Alert.alert_type == "hanging_payment",
        )
    )
    duplicate_count = result.scalar_one()
    assert duplicate_count == 1


@pytest.mark.asyncio
async def test_notification_route_and_mark_read(client, db_session):
    registration = {
        "full_name": "Notify Merchant",
        "email": "notify@example.com",
        "phone": "+2348000000012",
        "password": "NotifyPass123!",
        "merchant_name": "Notify Store",
        "business_type": "services",
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
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    notification = await NotificationService.create_notification(
        db_session,
        merchant_id=merchant_id,
        channel="in_app",
        message="Test notification",
    )
    await db_session.commit()

    list_resp = await client.get("/api/v1/notifications", headers=headers)
    assert list_resp.status_code == 200
    notifications = list_resp.json()
    assert any(item["id"] == str(notification.id) for item in notifications)

    read_resp = await client.post(f"/api/v1/notifications/{notification.id}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["status"] == "read"


@pytest.mark.asyncio
async def test_provider_failure_spike_creates_alert(client):
    registration = {
        "full_name": "Spike Merchant",
        "email": "spike@example.com",
        "phone": "+2348000000013",
        "password": "SpikePass123!",
        "merchant_name": "Spike Store",
        "business_type": "services",
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
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect_response = await client.post(
        "/api/v1/providers/connect",
        json={
            "merchant_id": merchant_id,
            "provider_name": "paystack",
            "credentials": {"api_key": "pk_spike_test", "secret_key": "test-paystack-secret"},
        },
        headers=headers,
    )
    assert connect_response.status_code == 200

    secret = "test-paystack-secret"
    for event_id in [3001, 3002, 3003]:
        payload = {
            "event": "charge.failed",
            "data": {
                "id": event_id,
                "reference": f"SPIKE{event_id}",
                "amount": 1000,
                "currency": "NGN",
                "status": "failed",
                "channel": "card",
                "gateway_response": "Declined",
                "transaction_date": "2026-04-11T12:00:00",
                "customer": {"email": "customer@example.com", "phone": "+2348000000006", "first_name": "Customer", "last_name": "Example"},
                "metadata": {},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
        response = await client.post(
            "/webhooks/paystack",
            content=body,
            headers={"X-Paystack-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

    alerts_resp = await client.get("/api/v1/alerts?alert_type=provider_error", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert any(alert["alert_type"] == "provider_error" for alert in alerts)
