"""Tests for Payment Graph / Ontology API module."""
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
