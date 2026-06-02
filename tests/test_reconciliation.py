import uuid
from datetime import datetime, timedelta, timezone

import pytest

from bomipay.main import app
from bomipay.models.transaction import Transaction
from bomipay.models.user import Role
from bomipay.services.auth import get_current_active_user


class DummyUser:
    def __init__(self, role: Role, merchant_id: str):
        self.role = role
        self.merchant_id = merchant_id


@pytest.mark.asyncio
async def test_import_expected_payments_json(client):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    payload = {
        "expected_payments": [
            {
                "reference": "INV-1001",
                "amount": 5000,
                "currency": "NGN",
                "due_date": datetime.now(timezone.utc).isoformat(),
                "customer_name": "Amina",
                "customer_email": "amina@example.com",
            },
            {
                "reference": "INV-1002",
                "amount": 7500,
                "currency": "NGN",
                "due_date": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }

    response = await client.post(
        "/api/v1/reconciliation/expected-payments/import",
        json=payload,
        params={"merchant_id": dummy.merchant_id},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["rows_received"] == 2
    assert result["rows_inserted"] == 2
    assert result["rows_skipped"] == 0
    assert result["rows_rejected"] == 0
    assert result["errors"] == []

    list_response = await client.get(
        "/api/v1/reconciliation/expected-payments",
        params={"merchant_id": dummy.merchant_id},
    )
    assert list_response.status_code == 200
    payments = list_response.json()
    assert len(payments) == 2
    assert any(item["reference"] == "INV-1001" for item in payments)
    assert any(item["reference"] == "INV-1002" for item in payments)

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_import_expected_payments_idempotency_and_alias(client):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    payload = {
        "expected_payments": [
            {
                "reference": "INV-3001",
                "amount": 9000,
                "currency": "NGN",
                "due_date": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    first = await client.post(
        "/api/v1/reconciliation/import",
        json=payload,
        params={"merchant_id": dummy.merchant_id},
    )
    assert first.status_code == 200
    assert first.json()["rows_inserted"] == 1
    assert first.json()["rows_skipped"] == 0

    second = await client.post(
        "/api/v1/reconciliation/import",
        json=payload,
        params={"merchant_id": dummy.merchant_id},
    )
    assert second.status_code == 200
    assert second.json()["rows_inserted"] == 0
    assert second.json()["rows_skipped"] == 1
    assert second.json()["rows_received"] == 1

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_import_invalid_rows_are_rejected_with_errors(client):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    payload = {
        "expected_payments": [
            {
                "reference": "INV-4001",
                "amount": 1000,
                "currency": "NGN",
                "due_date": datetime.now(timezone.utc).isoformat(),
            },
            {
                "reference": "INV-4002",
                "amount": "not-a-number",
                "currency": "NGN",
                "due_date": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }

    response = await client.post(
        "/api/v1/reconciliation/import",
        json=payload,
        params={"merchant_id": dummy.merchant_id},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["rows_received"] == 2
    assert result["rows_inserted"] == 1
    assert result["rows_rejected"] == 1
    assert len(result["errors"]) == 1

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_results_and_export_endpoints(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-7001",
        internal_reference="INV-7001",
        external_reference="INV-7001",
        currency="NGN",
        amount=8000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [{
            "reference": "INV-7001",
            "amount": 8000,
            "currency": "NGN",
            "due_date": (now - timedelta(days=1)).isoformat(),
        }]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Export Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_response.status_code == 200
    results = results_response.json()
    assert len(results) == 1
    assert results[0]["match_status"] == "matched"

    export_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/export",
        params={"merchant_id": dummy.merchant_id},
    )
    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported == results

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_duplicate_transaction_is_marked_duplicate(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-8001",
        internal_reference="INV-8001",
        external_reference="INV-8001",
        currency="NGN",
        amount=11000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [
            {
                "reference": "INV-8001",
                "amount": 11000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
                "customer_email": "finance@example.com",
            },
            {
                "reference": "INV-8001-ALT",
                "amount": 11000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
                "customer_email": "finance@example.com",
            },
        ]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Duplicate Transaction Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    statuses = [row["match_status"] for row in results_response.json()]
    assert statuses.count("matched") == 1
    assert statuses.count("duplicate") == 1

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_ambiguous_exact_matches_returns_ambiguous(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    for idx in range(2):
        transaction = Transaction(
            merchant_id=dummy.merchant_id,
            provider_name="paystack",
            provider_transaction_id=f"PS-900{idx}",
            internal_reference="INV-9001",
            external_reference="INV-9001",
            currency="NGN",
            amount=15000,
            status="success",
        )
        db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [
            {
                "reference": "INV-9001",
                "amount": 15000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
            }
        ]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Ambiguous Exact Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_response.status_code == 200
    assert results_response.json()[0]["match_status"] == "ambiguous"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_underpaid_overpaid_matches(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-10001",
        internal_reference="INV-10001",
        external_reference="INV-10001",
        currency="NGN",
        amount=13000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [
            {
                "reference": "INV-10001",
                "amount": 12000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
            }
        ]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Underpaid Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_response.status_code == 200
    assert results_response.json()[0]["match_status"] == "overpaid"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_underpaid_match(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-10002",
        internal_reference="INV-10002",
        external_reference="INV-10002",
        currency="NGN",
        amount=9000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [
            {
                "reference": "INV-10002",
                "amount": 10000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
            }
        ]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Underpaid Match Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_response.status_code == 200
    assert results_response.json()[0]["match_status"] == "underpaid"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_weak_match_by_amount_and_date_window(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-11001",
        internal_reference="REF-11001",
        external_reference="REF-11001",
        currency="NGN",
        amount=14000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [
            {
                "reference": "INV-11001",
                "amount": 14000,
                "currency": "NGN",
                "due_date": (now - timedelta(days=1)).isoformat(),
            }
        ]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Weak Match Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    results_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_response.status_code == 200
    assert results_response.json()[0]["match_status"] == "weak"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_repeatability_creates_separate_runs(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    expected_payment = {
        "reference": "INV-1002",
        "amount": 12000,
        "currency": "NGN",
        "due_date": (now - timedelta(days=1)).isoformat(),
    }
    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [expected_payment]},
        params={"merchant_id": dummy.merchant_id},
    )

    first_run = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Repeatability A",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    second_run = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Repeatability B",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert first_run.status_code == 200
    assert second_run.status_code == 200
    assert first_run.json()["id"] != second_run.json()["id"]

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_matches_transactions(client, db_session):
    dummy = DummyUser(Role.admin, str(uuid.uuid4()))
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = datetime.now(timezone.utc)
    transaction = Transaction(
        merchant_id=dummy.merchant_id,
        provider_name="paystack",
        provider_transaction_id="PS-0001",
        internal_reference="INV-2001",
        external_reference="INV-2001",
        currency="NGN",
        amount=12000,
        status="success",
    )
    db_session.add(transaction)
    await db_session.commit()

    expected_payment = {
        "reference": "INV-2001",
        "amount": 12000,
        "currency": "NGN",
        "due_date": (now - timedelta(days=1)).isoformat(),
    }

    import_response = await client.post(
        "/api/v1/reconciliation/expected-payments/import",
        json={"expected_payments": [expected_payment]},
        params={"merchant_id": dummy.merchant_id},
    )
    assert import_response.status_code == 200

    run_response = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": (now + timedelta(days=1)).isoformat(),
            "run_name": "Test Reconciliation",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["merchant_id"] == dummy.merchant_id

    summary_response = await client.get(
        f"/api/v1/reconciliation/runs/{run_payload['id']}/summary",
        params={"merchant_id": dummy.merchant_id},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["expected_count"] == 1
    assert summary["matched_count"] == 1
    assert summary["unmatched_count"] == 0
    assert summary["total_expected_amount"] == 12000
    assert summary["total_matched_amount"] == 12000

    app.dependency_overrides.pop(get_current_active_user, None)
