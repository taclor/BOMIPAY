"""Tests for Action Center API."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from bomipay.models.transaction import Transaction, TransactionStatus
from bomipay.models.bank_statement import BankStatementImport, BankStatementImportStatus
from bomipay.models.bank_account import BankAccount, BankAccountVerificationStatus, BankAccountStatus
from bomipay.models.data_source import DataSource, DataSourceStatus


async def _register_and_login(client, email: str, phone: str, merchant_name: str = ""):
    name = merchant_name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Action User",
            "email": email,
            "phone": phone,
            "password": "ActionPass123!",
            "merchant_name": name,
        },
    )
    assert reg.status_code == 201, reg.text
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ActionPass123!"},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# test_get_actions_empty_merchant
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_empty_merchant(client):
    """A new merchant with no data should still get sensible default actions."""
    mid, headers = await _register_and_login(
        client, "ac_empty@example.com", "+2348010000001"
    )
    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    action_types = [a["action_type"] for a in data["actions"]]
    # New merchant with no bank statement import → upload prompt appears
    assert "upload_bank_statement" in action_types


# ---------------------------------------------------------------------------
# test_get_actions_requires_auth
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_requires_auth(client):
    """Unauthenticated requests must be rejected with 401."""
    resp = await client.get("/api/v1/action-center")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# test_get_actions_tenant_isolation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_tenant_isolation(client):
    """Merchant A should not be able to read Merchant B's actions."""
    mid_a, headers_a = await _register_and_login(
        client, "ac_iso_a@example.com", "+2348010000002", "AC Iso A"
    )
    mid_b, _ = await _register_and_login(
        client, "ac_iso_b@example.com", "+2348010000003", "AC Iso B"
    )
    resp = await client.get(
        f"/api/v1/action-center?merchant_id={mid_b}", headers=headers_a
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# test_get_actions_with_failed_transactions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_with_failed_transactions(client, db_session):
    """After inserting a failed transaction, investigate_failed_payment should appear."""
    mid, headers = await _register_and_login(
        client, "ac_failed_txn@example.com", "+2348010000004"
    )
    txn = Transaction(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="test_provider",
        provider_transaction_id=f"prov-{uuid.uuid4()}",
        currency="NGN",
        amount=10000,
        status=TransactionStatus.failed.value,
    )
    db_session.add(txn)
    await db_session.commit()

    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    action_types = [a["action_type"] for a in resp.json()["actions"]]
    assert "investigate_failed_payment" in action_types


# ---------------------------------------------------------------------------
# test_get_actions_with_pending_imports
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_with_pending_imports(client, db_session):
    """After inserting an uploaded BankStatementImport, process_bank_statement should appear."""
    mid, headers = await _register_and_login(
        client, "ac_pending_imp@example.com", "+2348010000005"
    )
    stmt_import = BankStatementImport(
        id=uuid.uuid4(),
        merchant_id=mid,
        file_name="statement.csv",
        file_type="csv",
        status=BankStatementImportStatus.uploaded.value,
    )
    db_session.add(stmt_import)
    await db_session.commit()

    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    action_types = [a["action_type"] for a in resp.json()["actions"]]
    assert "process_bank_statement" in action_types
    assert "upload_bank_statement" not in action_types


# ---------------------------------------------------------------------------
# test_get_actions_structure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_structure(client):
    """Each action must contain the required canonical keys."""
    mid, headers = await _register_and_login(
        client, "ac_structure@example.com", "+2348010000006"
    )
    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    required_keys = {"action_type", "priority", "title", "description", "entity_type", "count"}
    for action in resp.json()["actions"]:
        missing = required_keys - action.keys()
        assert not missing, f"Action {action.get('action_type')} missing keys: {missing}"
        assert isinstance(action["priority"], int)
        assert isinstance(action["count"], int)
        assert action["action_type"]
        assert action["title"]


# ---------------------------------------------------------------------------
# test_get_action_stats_empty
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_action_stats_empty(client):
    """Stats endpoint returns sensible structure for a new merchant."""
    mid, headers = await _register_and_login(
        client, "ac_stats_empty@example.com", "+2348010000007"
    )
    resp = await client.get("/api/v1/action-center/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "critical" in data
    assert "high_priority" in data
    assert "by_type" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["critical"], int)
    assert isinstance(data["high_priority"], int)
    assert isinstance(data["by_type"], dict)
    # New merchant has zero critical and high_priority items
    assert data["critical"] == 0
    assert data["high_priority"] == 0


# ---------------------------------------------------------------------------
# test_get_action_stats_requires_auth
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_action_stats_requires_auth(client):
    """Stats endpoint must reject unauthenticated requests with 401."""
    resp = await client.get("/api/v1/action-center/stats")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# test_dismiss_action
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dismiss_action(client):
    """POST /action-center/{type}/dismiss should return dismissed=True."""
    mid, headers = await _register_and_login(
        client, "ac_dismiss@example.com", "+2348010000008"
    )
    resp = await client.post(
        "/api/v1/action-center/upload_bank_statement/dismiss", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dismissed"] is True
    assert data["action_type"] == "upload_bank_statement"


# ---------------------------------------------------------------------------
# test_dismiss_action_requires_auth
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dismiss_action_requires_auth(client):
    """Dismiss endpoint must reject unauthenticated requests with 401."""
    resp = await client.post("/api/v1/action-center/upload_bank_statement/dismiss")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# test_actions_sorted_by_priority
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_actions_sorted_by_priority(client, db_session):
    """Actions should be returned sorted by priority ascending (most urgent first)."""
    mid, headers = await _register_and_login(
        client, "ac_sorted@example.com", "+2348010000009"
    )
    # Add a failed transaction (priority 1) alongside the default upload action (priority 5)
    txn = Transaction(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="test_provider",
        provider_transaction_id=f"prov-sort-{uuid.uuid4()}",
        currency="NGN",
        amount=5000,
        status=TransactionStatus.failed.value,
    )
    db_session.add(txn)
    await db_session.commit()

    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    priorities = [a["priority"] for a in resp.json()["actions"]]
    assert priorities == sorted(priorities), "Actions must be sorted by priority ascending"


# ---------------------------------------------------------------------------
# test_get_actions_with_unverified_bank_accounts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_with_unverified_bank_accounts(client, db_session):
    """Unverified bank accounts trigger verify_bank_account action."""
    mid, headers = await _register_and_login(
        client, "ac_unverified_ba@example.com", "+2348010000010"
    )
    bank_acct = BankAccount(
        id=uuid.uuid4(),
        merchant_id=mid,
        bank_name="Test Bank",
        account_number_encrypted="encrypted-1234",
        account_number_last4="1234",
        account_name="Test Merchant",
        verification_status=BankAccountVerificationStatus.unverified.value,
        status=BankAccountStatus.active.value,
    )
    db_session.add(bank_acct)
    await db_session.commit()

    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    action_types = [a["action_type"] for a in resp.json()["actions"]]
    assert "verify_bank_account" in action_types


# ---------------------------------------------------------------------------
# test_get_actions_with_error_data_source
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actions_with_error_data_source(client, db_session):
    """Data sources in error state trigger reconnect_data_source action."""
    mid, headers = await _register_and_login(
        client, "ac_err_ds@example.com", "+2348010000011"
    )
    ds = DataSource(
        id=uuid.uuid4(),
        merchant_id=mid,
        source_type="provider_api",
        display_name="Broken Provider",
        status=DataSourceStatus.error.value,
    )
    db_session.add(ds)
    await db_session.commit()

    resp = await client.get("/api/v1/action-center", headers=headers)
    assert resp.status_code == 200
    action_types = [a["action_type"] for a in resp.json()["actions"]]
    assert "reconnect_data_source" in action_types


# ---------------------------------------------------------------------------
# test_get_action_stats_counts_correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_action_stats_counts_correctly(client, db_session):
    """Stats critical count increases when failed transactions are present."""
    mid, headers = await _register_and_login(
        client, "ac_stats_count@example.com", "+2348010000012"
    )
    for i in range(2):
        db_session.add(Transaction(
            id=uuid.uuid4(),
            merchant_id=mid,
            provider_name="test_provider",
            provider_transaction_id=f"prov-stat-{i}-{uuid.uuid4()}",
            currency="NGN",
            amount=1000,
            status=TransactionStatus.failed.value,
        ))
    await db_session.commit()

    resp = await client.get("/api/v1/action-center/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["critical"] >= 1
    assert data["total"] >= 1
    assert "investigate_failed_payment" in data["by_type"]
