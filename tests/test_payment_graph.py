"""Tests for Payment Graph / Ontology API module."""
import uuid
from datetime import datetime, timezone

import pytest


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Graph User",
            "email": email,
            "phone": phone,
            "password": "GraphPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "GraphPass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


def _assert_graph_shape(data: dict):
    """Assert the graph response contains nodes and edges lists."""
    assert "nodes" in data, "Graph must have 'nodes'"
    assert "edges" in data, "Graph must have 'edges'"
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    for node in data["nodes"]:
        assert "id" in node
        assert "type" in node
    for edge in data["edges"]:
        assert "from" in edge
        assert "to" in edge
        assert "relationship" in edge


@pytest.mark.asyncio
async def test_merchant_overview_graph(client):
    mid, headers = await _register_and_login(
        client, "graph_merchant@example.com", "+2348006000001"
    )
    resp = await client.get(
        f"/api/v1/payment-graph/merchants/{mid}/overview", headers=headers
    )
    assert resp.status_code == 200
    _assert_graph_shape(resp.json())


@pytest.mark.asyncio
async def test_merchant_overview_graph_tenant_isolation(client):
    mid_a, headers_a = await _register_and_login(
        client, "graph_a@example.com", "+2348006000002", "Graph A"
    )
    mid_b, _ = await _register_and_login(
        client, "graph_b@example.com", "+2348006000003", "Graph B"
    )

    # Merchant A cannot view Merchant B's graph
    resp = await client.get(
        f"/api/v1/payment-graph/merchants/{mid_b}/overview", headers=headers_a
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_transaction_graph_not_found(client):
    mid, headers = await _register_and_login(
        client, "graph_txn_404@example.com", "+2348006000004"
    )
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(
        f"/api/v1/payment-graph/transactions/{fake_id}", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_incident_graph_not_found(client):
    _, headers = await _register_and_login(
        client, "graph_inc_404@example.com", "+2348006000005"
    )
    fake_id = "00000000-0000-0000-0000-000000000001"
    resp = await client.get(
        f"/api/v1/payment-graph/incidents/{fake_id}", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_graph_requires_auth(client):
    fake_id = "00000000-0000-0000-0000-000000000002"
    resp = await client.get(f"/api/v1/payment-graph/merchants/{fake_id}/overview")
    assert resp.status_code == 401


# --- New tests ---


@pytest.mark.asyncio
async def test_settlement_graph_not_found(client):
    mid, headers = await _register_and_login(
        client, "graph_settle_404@example.com", "+2348006000010"
    )
    fake_id = "00000000-0000-0000-0000-000000000010"
    resp = await client.get(
        f"/api/v1/payment-graph/settlements/{fake_id}",
        params={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_settlement_graph_requires_auth(client):
    fake_id = "00000000-0000-0000-0000-000000000011"
    resp = await client.get(
        f"/api/v1/payment-graph/settlements/{fake_id}",
        params={"merchant_id": fake_id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_merchant_network_graph(client, db_session):
    from bomipay.models.transaction import Transaction
    from bomipay.models.reconciliation import Settlement

    mid, headers = await _register_and_login(
        client, "graph_network@example.com", "+2348006000012"
    )

    # Seed a transaction so the network graph has something
    txn = Transaction(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="test_provider",
        provider_transaction_id="NET-TXN-001",
        amount=5000,
        currency="NGN",
        status="success",
    )
    db_session.add(txn)

    settle = Settlement(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="test_provider",
        settlement_reference="NET-SETTLE-001",
        amount=5000,
        currency="NGN",
        settled_at=datetime.now(timezone.utc),
    )
    db_session.add(settle)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/payment-graph/merchants/{mid}/network", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_graph_shape(data)
    node_types = {n["type"] for n in data["nodes"]}
    assert "merchant" in node_types


@pytest.mark.asyncio
async def test_merchant_network_requires_auth(client):
    fake_id = "00000000-0000-0000-0000-000000000013"
    resp = await client.get(f"/api/v1/payment-graph/merchants/{fake_id}/network")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_merchant_network_tenant_isolation(client):
    mid_a, headers_a = await _register_and_login(
        client, "graph_net_a@example.com", "+2348006000014", "NetA"
    )
    mid_b, _ = await _register_and_login(
        client, "graph_net_b@example.com", "+2348006000015", "NetB"
    )

    resp = await client.get(
        f"/api/v1/payment-graph/merchants/{mid_b}/network", headers=headers_a
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_transaction_graph_with_events(client, db_session):
    from bomipay.models.transaction import Transaction
    from bomipay.models.transaction_event import TransactionEvent

    mid, headers = await _register_and_login(
        client, "graph_txnevt@example.com", "+2348006000016"
    )

    txn_id = uuid.uuid4()
    txn = Transaction(
        id=txn_id,
        merchant_id=mid,
        provider_name="stripe",
        provider_transaction_id="EVT-TXN-001",
        amount=10000,
        currency="NGN",
        status="success",
    )
    db_session.add(txn)

    evt = TransactionEvent(
        id=uuid.uuid4(),
        transaction_id=txn_id,
        provider_name="stripe",
        event_type="payment.captured",
        provider_payload={"amount": 10000},
        provider_event_id="stripe_evt_001",
    )
    db_session.add(evt)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/payment-graph/transactions/{txn_id}",
        params={"merchant_id": mid},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_graph_shape(data)
    node_types = {n["type"] for n in data["nodes"]}
    assert "transaction" in node_types
    assert "transaction_event" in node_types
    event_edges = [e for e in data["edges"] if e["relationship"] == "has_event"]
    assert len(event_edges) >= 1
