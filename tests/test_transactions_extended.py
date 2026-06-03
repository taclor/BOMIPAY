import uuid

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


def _merchant_dummy() -> DummyUser:
    return DummyUser(Role.merchant_user, str(uuid.uuid4()))


def _make_transaction(merchant_id: str, **kwargs) -> Transaction:
    defaults = dict(
        provider_name="paystack",
        provider_transaction_id=str(uuid.uuid4()),
        internal_reference=str(uuid.uuid4()),
        external_reference=str(uuid.uuid4()),
        currency="NGN",
        amount=5000,
        status="success",
    )
    defaults.update(kwargs)
    return Transaction(merchant_id=merchant_id, **defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_transactions_empty(client):
    """A fresh merchant with no transactions gets an empty list."""
    dummy = _merchant_dummy()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 200
    assert resp.json() == []

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_list_transactions_requires_auth(client):
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_transactions_tenant_isolation(client, db_session):
    """Merchant A must not see Merchant B's transactions."""
    merchant_a = _merchant_dummy()
    merchant_b = _merchant_dummy()

    tx = _make_transaction(
        merchant_b.merchant_id,
        internal_reference="ISO-TX-001",
        external_reference="ISO-TX-001",
    )
    db_session.add(tx)
    await db_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: merchant_a
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 200
    refs = [t["internal_reference"] for t in resp.json()]
    assert "ISO-TX-001" not in refs

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_transaction_detail_not_found(client):
    dummy = _merchant_dummy()
    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get(f"/api/v1/transactions/{uuid.uuid4()}")
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_list_transactions_status_filter(client, db_session):
    dummy = _merchant_dummy()

    db_session.add(_make_transaction(dummy.merchant_id, status="success", internal_reference="FILT-OK-1", external_reference="FILT-OK-1", provider_transaction_id="FILT-OK-P1"))
    db_session.add(_make_transaction(dummy.merchant_id, status="failed", internal_reference="FILT-FAIL-1", external_reference="FILT-FAIL-1", provider_transaction_id="FILT-FAIL-P1"))
    await db_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: dummy

    ok_resp = await client.get("/api/v1/transactions", params={"status": "success"})
    assert ok_resp.status_code == 200
    statuses = [t["status"] for t in ok_resp.json()]
    assert all(s == "success" for s in statuses)
    assert any(True for t in ok_resp.json() if t["internal_reference"] == "FILT-OK-1")

    fail_resp = await client.get("/api/v1/transactions", params={"status": "failed"})
    assert fail_resp.status_code == 200
    assert all(t["status"] == "failed" for t in fail_resp.json())

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_list_transactions_provider_filter(client, db_session):
    dummy = _merchant_dummy()

    db_session.add(_make_transaction(dummy.merchant_id, provider_name="paystack", internal_reference="PROV-PS-1", external_reference="PROV-PS-1", provider_transaction_id="PROV-PS-P1"))
    db_session.add(_make_transaction(dummy.merchant_id, provider_name="flutterwave", internal_reference="PROV-FW-1", external_reference="PROV-FW-1", provider_transaction_id="PROV-FW-P1"))
    await db_session.commit()

    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get("/api/v1/transactions", params={"provider_name": "paystack"})
    assert resp.status_code == 200
    providers = [t["provider_name"] for t in resp.json()]
    assert all(p == "paystack" for p in providers)

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_transaction_detail_returns_correct_record(client, db_session):
    dummy = _merchant_dummy()

    tx = _make_transaction(dummy.merchant_id, internal_reference="DETAIL-TX-001", external_reference="DETAIL-TX-001", provider_transaction_id="DETAIL-P-001")
    db_session.add(tx)
    await db_session.commit()
    # expire_on_commit=False — access id directly without triggering autobegin
    tx_id = str(tx.id)

    app.dependency_overrides[get_current_active_user] = lambda: dummy

    resp = await client.get(f"/api/v1/transactions/{tx_id}")
    assert resp.status_code == 200
    assert resp.json()["internal_reference"] == "DETAIL-TX-001"

    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_transaction_detail_tenant_isolation(client, db_session):
    """Merchant A cannot fetch Merchant B's transaction by ID."""
    owner = _merchant_dummy()
    intruder = _merchant_dummy()

    tx = _make_transaction(owner.merchant_id, internal_reference="ISOL-OWN-001", external_reference="ISOL-OWN-001", provider_transaction_id="ISOL-OWN-P1")
    db_session.add(tx)
    await db_session.commit()
    tx_id = str(tx.id)

    app.dependency_overrides[get_current_active_user] = lambda: intruder
    resp = await client.get(f"/api/v1/transactions/{tx_id}")
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_current_active_user, None)
