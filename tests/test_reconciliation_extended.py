import uuid
from datetime import datetime, timedelta, timezone

import pytest

from bomipay.main import app
from bomipay.models.transaction import Transaction
from bomipay.models.user import Role
from bomipay.services.auth import get_current_active_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyUser:
    def __init__(self, role: Role, merchant_id: str):
        self.role = role
        self.merchant_id = merchant_id


def _admin() -> DummyUser:
    return DummyUser(Role.admin, str(uuid.uuid4()))


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconciliation_run_empty_merchant(client):
    """Running reconciliation for a merchant with zero transactions and zero
    expected payments should succeed and return a completed run."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = _now()
    resp = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=7)).isoformat(),
            "date_to": now.isoformat(),
            "run_name": "Empty Merchant Run",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["merchant_id"] == dummy.merchant_id

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_list_reconciliation_runs(client):
    """GET /reconciliation/runs should return the list of runs for the merchant."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = _now()
    run_body = {
        "date_from": (now - timedelta(days=3)).isoformat(),
        "date_to": now.isoformat(),
        "run_name": "List Runs Test",
    }
    create_resp = await client.post(
        "/api/v1/reconciliation/runs",
        json=run_body,
        params={"merchant_id": dummy.merchant_id},
    )
    assert create_resp.status_code == 200
    run_id = create_resp.json()["id"]

    list_resp = await client.get(
        "/api/v1/reconciliation/runs",
        params={"merchant_id": dummy.merchant_id},
    )
    assert list_resp.status_code == 200
    runs = list_resp.json()
    assert isinstance(runs, list)
    assert any(r["id"] == run_id for r in runs)

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_tenant_isolation(client):
    """Merchant A must not see Merchant B's reconciliation runs."""
    merchant_a = _admin()
    merchant_b = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: merchant_b

    now = _now()
    create_resp = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=1)).isoformat(),
            "date_to": now.isoformat(),
            "run_name": "Merchant B Isolation Run",
        },
        params={"merchant_id": merchant_b.merchant_id},
    )
    assert create_resp.status_code == 200
    b_run_id = create_resp.json()["id"]

    # Merchant A queries their own runs — should not include merchant B's run
    app.dependency_overrides[get_current_active_user] = lambda: merchant_a
    list_resp = await client.get(
        "/api/v1/reconciliation/runs",
        params={"merchant_id": merchant_a.merchant_id},
    )
    assert list_resp.status_code == 200
    ids = [r["id"] for r in list_resp.json()]
    assert b_run_id not in ids

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_get_run_not_found(client):
    """Getting a non-existent run ID should return 404."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get(
        f"/api/v1/reconciliation/runs/{uuid.uuid4()}",
        params={"merchant_id": dummy.merchant_id},
    )
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_results_empty_for_new_run(client):
    """A run with no expected payments should produce an empty results list."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = _now()
    run_resp = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": now.isoformat(),
            "run_name": "Empty Results Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    results_resp = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/results",
        params={"merchant_id": dummy.merchant_id},
    )
    assert results_resp.status_code == 200
    assert results_resp.json() == []

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_run_summary_unmatched(client):
    """A run where no transaction matches the expected payment should report unmatched count."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = _now()
    # Import an expected payment with a unique reference that has no matching transaction
    await client.post(
        "/api/v1/reconciliation/import",
        json={"expected_payments": [{
            "reference": f"UNMATCHED-{uuid.uuid4().hex[:8]}",
            "amount": 99999,
            "currency": "NGN",
            "due_date": (now - timedelta(days=1)).isoformat(),
        }]},
        params={"merchant_id": dummy.merchant_id},
    )

    run_resp = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": (now - timedelta(days=3)).isoformat(),
            "date_to": (now + timedelta(hours=1)).isoformat(),
            "run_name": "Unmatched Summary Test",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    summary_resp = await client.get(
        f"/api/v1/reconciliation/runs/{run_id}/summary",
        params={"merchant_id": dummy.merchant_id},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["expected_count"] >= 1
    assert summary["unmatched_count"] >= 1

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_reconciliation_date_from_must_precede_date_to(client):
    """Creating a run where date_from >= date_to must return 400."""
    dummy = _admin()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    now = _now()
    resp = await client.post(
        "/api/v1/reconciliation/runs",
        json={
            "date_from": now.isoformat(),
            "date_to": (now - timedelta(days=1)).isoformat(),
            "run_name": "Invalid Date Order",
        },
        params={"merchant_id": dummy.merchant_id},
    )
    assert resp.status_code == 400

    app.dependency_overrides.pop(get_current_active_user, None)
