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
    for key in ("query", "query_category", "merchant_id", "answer", "confidence_score_bps",
                "cited_records", "suggested_actions", "context_used", "generated_at"):
        assert key in data, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_ai_confidence_is_between_0_and_10000(client):
    mid, headers = await _register_and_login(
        client, "ai_conf@example.com", "+2348007000002"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "Which provider is causing most problems?"},
        headers=headers,
    )
    assert resp.status_code == 200
    confidence = resp.json()["confidence_score_bps"]
    assert isinstance(confidence, int)
    assert 0 <= confidence <= 10000


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


# ---------------------------------------------------------------------------
# New category routing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_incident_analysis_category(client):
    mid, headers = await _register_and_login(
        client, "ai_inc_cat@example.com", "+2348007000013"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "show me active incidents"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "incident_analysis"


@pytest.mark.asyncio
async def test_ai_incident_analysis_response(client):
    mid, headers = await _register_and_login(
        client, "ai_inc_resp@example.com", "+2348007000014"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "show me active incidents"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("answer", "confidence_score_bps", "cited_records", "suggested_actions", "context_used"):
        assert key in data, f"Missing key: {key}"
    ctx = data["context_used"]
    assert "open_incidents" in ctx
    assert "by_severity" in ctx
    assert len(data["answer"]) > 0


@pytest.mark.asyncio
async def test_ai_trend_analysis_category(client):
    mid, headers = await _register_and_login(
        client, "ai_trend_cat@example.com", "+2348007000015"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "show me trend over last month"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "trend_analysis"


@pytest.mark.asyncio
async def test_ai_trend_analysis_response(client):
    mid, headers = await _register_and_login(
        client, "ai_trend_resp@example.com", "+2348007000016"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "show me volume trend"},
        headers=headers,
    )
    assert resp.status_code == 200
    ctx = resp.json()["context_used"]
    assert "total_transactions" in ctx
    assert "total_volume" in ctx
    assert "failed_count" in ctx
    assert isinstance(ctx["total_transactions"], int)
    assert isinstance(ctx["total_volume"], int)
    assert isinstance(ctx["failed_count"], int)


@pytest.mark.asyncio
async def test_ai_data_health_category(client):
    mid, headers = await _register_and_login(
        client, "ai_dh_cat@example.com", "+2348007000017"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "check data source health"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["query_category"] == "data_health"


@pytest.mark.asyncio
async def test_ai_data_health_response(client):
    mid, headers = await _register_and_login(
        client, "ai_dh_resp@example.com", "+2348007000018"
    )
    resp = await client.post(
        "/api/v1/ai-assistant/query",
        json={"merchant_id": mid, "query": "check data source health"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("answer", "confidence_score_bps", "cited_records", "suggested_actions", "context_used"):
        assert key in data, f"Missing key: {key}"
    ctx = data["context_used"]
    assert "total_data_sources" in ctx
    assert "healthy" in ctx
    assert "error" in ctx
    assert "provider_accounts" in ctx
    assert "recent_sync_failures" in ctx


@pytest.mark.asyncio
async def test_ai_categories_endpoint(client):
    resp = await client.get("/api/v1/ai-assistant/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    categories = data["categories"]
    assert isinstance(categories, list)
    assert len(categories) >= 7
    names = [c["name"] for c in categories]
    for expected in ("money_at_risk", "provider_problems", "settlement_mismatch", "what_to_do",
                     "incident_analysis", "trend_analysis", "data_health"):
        assert expected in names, f"Missing category: {expected}"
    for cat in categories:
        assert "name" in cat
        assert "keywords" in cat
        assert "description" in cat


@pytest.mark.asyncio
async def test_ai_health_endpoint(client):
    resp = await client.get("/api/v1/ai-assistant/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "categories_supported" in data
    assert data["categories_supported"] == 7
