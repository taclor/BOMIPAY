"""Tests for AI Assistant Extension (Module 11)."""
import pytest


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "AI User",
            "email": email,
            "phone": phone,
            "password": "AIPass123!Secure",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AIPass123!Secure"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Structure / schema tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_query_returns_required_fields(client):
    mid, headers = await _register_and_login(
        client, "ai_struct@example.com", "+2348007000001"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Why is my money at risk?"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("query", "query_category", "merchant_id", "answer", "confidence",
                "cited_records", "suggested_actions", "context_used", "generated_at"):
        assert key in data, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_ai_confidence_is_between_0_and_1(client):
    mid, headers = await _register_and_login(
        client, "ai_conf@example.com", "+2348007000002"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Which provider is causing most problems?"},
        headers=headers,
    )
    assert resp.status_code == 200
    confidence = resp.json()["confidence"]
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_ai_cited_records_have_type_id_summary(client):
    mid, headers = await _register_and_login(
        client, "ai_cite@example.com", "+2348007000003"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Show me all unresolved money issues."},
        headers=headers,
    )
    assert resp.status_code == 200
    for record in resp.json()["cited_records"]:
        assert "type" in record
        assert "id" in record
        assert "summary" in record


@pytest.mark.asyncio
async def test_ai_suggested_actions_have_required_fields(client):
    mid, headers = await _register_and_login(
        client, "ai_actions@example.com", "+2348007000004"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "What should I do first today?"},
        headers=headers,
    )
    assert resp.status_code == 200
    for action in resp.json()["suggested_actions"]:
        assert "action_type" in action
        assert "description" in action
        assert "priority" in action


# ---------------------------------------------------------------------------
# Query category routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_money_at_risk_query_category(client):
    mid, headers = await _register_and_login(
        client, "ai_mar@example.com", "+2348007000005"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Why is my money at risk?"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "money_at_risk"


@pytest.mark.asyncio
async def test_ai_provider_query_category(client):
    mid, headers = await _register_and_login(
        client, "ai_prov@example.com", "+2348007000006"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Which provider is causing most problems?"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "provider_problems"


@pytest.mark.asyncio
async def test_ai_settlement_mismatch_query_category(client):
    mid, headers = await _register_and_login(
        client, "ai_sett@example.com", "+2348007000007"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Why is this settlement not matching my bank statement?"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "settlement_mismatch"


@pytest.mark.asyncio
async def test_ai_what_to_do_query_category(client):
    mid, headers = await _register_and_login(
        client, "ai_todo@example.com", "+2348007000008"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "What should I do first today?"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "what_to_do"


# ---------------------------------------------------------------------------
# Safety / isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_requires_auth(client):
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": "00000000-0000-0000-0000-000000000000", "query": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ai_tenant_isolation(client):
    mid_a, headers_a = await _register_and_login(
        client, "ai_iso_a@example.com", "+2348007000009", "AI Iso A"
    )
    mid_b, _ = await _register_and_login(
        client, "ai_iso_b@example.com", "+2348007000010", "AI Iso B"
    )
    # User A cannot query merchant B's data
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid_b, "query": "Why is my money at risk?"},
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ai_answer_is_not_empty(client):
    mid, headers = await _register_and_login(
        client, "ai_nonempty@example.com", "+2348007000011"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Show me all unresolved money issues."},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["answer"]) > 0


@pytest.mark.asyncio
async def test_ai_does_not_return_floats_for_money(client):
    mid, headers = await _register_and_login(
        client, "ai_nofloat@example.com", "+2348007000012"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Why is my money at risk?"},
        headers=headers,
    )
    assert resp.status_code == 200
    ctx = resp.json()["context_used"]
    # All monetary values in context must be integers (minor units)
    for key in ("failed_amount_minor", "pending_amount_minor", "total_at_risk_minor"):
        if key in ctx:
            assert isinstance(ctx[key], int), f"{key} must be int, got {type(ctx[key])}"
