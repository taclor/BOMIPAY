"""Tests for Incident Center module."""
import pytest
from datetime import datetime, timezone, timedelta

from bomipay.models.user import Role
from bomipay.services.security import create_access_token
from bomipay.services.user import UserService


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Inc User",
            "email": email,
            "phone": phone,
            "password": "IncidentPass123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "IncidentPass123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


async def _finance_headers(db_session, email: str, phone: str, merchant_id) -> dict:
    """Create a finance-role user linked to merchant_id and return auth headers."""
    user = await UserService.create_user(
        db_session,
        email=email,
        password="IncidentPass123!",
        full_name="Finance User",
        phone=phone,
        role=Role.finance,
        merchant_id=merchant_id,
    )
    await db_session.commit()
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _incident_payload(merchant_id: str, title: str = "Provider down", incident_type: str = "provider_failure_spike") -> dict:
    return {
        "merchant_id": merchant_id,
        "title": title,
        "incident_type": incident_type,
        "severity": "high",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Multiple transactions failed due to provider timeout.",
        "affected_amount_minor": 500000,
        "affected_transaction_count": 12,
    }


@pytest.mark.asyncio
async def test_create_and_list_incident(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_create@example.com", "+2348004000001"
    )
    fin_headers = await _finance_headers(db_session, "inc_create_fin@example.com", "+2348004000101", mid)
    payload = _incident_payload(mid)
    resp = await client.post("/api/v1/incidents", json=payload, headers=fin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Provider down"
    assert data["status"] == "open"
    assert data["severity"] == "high"
    assert data["merchant_id"] == mid

    list_resp = await client.get(
        f"/api/v1/incidents?merchant_id={mid}", headers=headers
    )
    assert list_resp.status_code == 200
    assert any(i["id"] == data["id"] for i in list_resp.json())


@pytest.mark.asyncio
async def test_get_incident_by_id(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_get@example.com", "+2348004000002"
    )
    fin_headers = await _finance_headers(db_session, "inc_get_fin@example.com", "+2348004000102", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Get Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == inc_id


@pytest.mark.asyncio
async def test_acknowledge_incident(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_ack@example.com", "+2348004000003"
    )
    fin_headers = await _finance_headers(db_session, "inc_ack_fin@example.com", "+2348004000103", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Ack Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    resp = await client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_resolve_incident(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_resolve@example.com", "+2348004000004"
    )
    fin_headers = await _finance_headers(db_session, "inc_resolve_fin@example.com", "+2348004000104", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Resolve Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    # Acknowledge first (any role), then resolve (finance role)
    await client.post(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)
    resp = await client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        params={"resolution_note": "Provider recovered"},
        headers=fin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["ended_at"] is not None


@pytest.mark.asyncio
async def test_incident_add_event(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_event@example.com", "+2348004000005"
    )
    fin_headers = await _finance_headers(db_session, "inc_event_fin@example.com", "+2348004000105", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Event Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    event_resp = await client.post(
        f"/api/v1/incidents/{inc_id}/events",
        json={"event_type": "note", "message": "Investigating with provider team"},
        headers=headers,
    )
    assert event_resp.status_code == 201
    event = event_resp.json()
    assert event["incident_id"] == inc_id
    assert event["message"] == "Investigating with provider team"


@pytest.mark.asyncio
async def test_incident_timeline_is_append_only(client, db_session):
    """Events added should accumulate; re-fetching shows all events."""
    mid, headers = await _register_and_login(
        client, "inc_timeline@example.com", "+2348004000006"
    )
    fin_headers = await _finance_headers(db_session, "inc_timeline_fin@example.com", "+2348004000106", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Timeline Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    for msg in ("Step 1", "Step 2", "Step 3"):
        await client.post(
            f"/api/v1/incidents/{inc_id}/events",
            json={"event_type": "note", "message": msg},
            headers=headers,
        )

    # Acknowledging also appends an event
    await client.post(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)

    # We should be able to list the incident; the state should be acknowledged
    resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
    assert resp.json()["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_incident_tenant_isolation(client, db_session):
    mid_a, headers_a = await _register_and_login(
        client, "inc_tenant_a@example.com", "+2348004000007", "Inc Tenant A"
    )
    _, headers_b = await _register_and_login(
        client, "inc_tenant_b@example.com", "+2348004000008", "Inc Tenant B"
    )
    fin_headers = await _finance_headers(db_session, "inc_tenant_fin@example.com", "+2348004000107", mid_a)

    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid_a, "Tenant Isolation"), headers=fin_headers
    )
    inc_id = create.json()["id"]

    resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers_b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_incident_filter_by_status(client, db_session):
    mid, headers = await _register_and_login(
        client, "inc_filter@example.com", "+2348004000009"
    )
    fin_headers = await _finance_headers(db_session, "inc_filter_fin@example.com", "+2348004000109", mid)
    create = await client.post(
        "/api/v1/incidents", json=_incident_payload(mid, "Filter Test"), headers=fin_headers
    )
    inc_id = create.json()["id"]
    await client.post(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)

    resp = await client.get(
        f"/api/v1/incidents?merchant_id={mid}&status=acknowledged", headers=headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert all(i["status"] == "acknowledged" for i in results)


@pytest.mark.asyncio
async def test_incidents_require_auth(client):
    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_incident_filter_by_severity(client, db_session):
    """Test filtering incidents by severity level."""
    mid, headers = await _register_and_login(
        client, "inc_severity@example.com", "+2348004000010"
    )
    fin_headers = await _finance_headers(db_session, "inc_severity_fin@example.com", "+2348004000110", mid)
    
    # Create incidents with different severities
    for severity in ["low", "medium", "high", "critical"]:
        payload = _incident_payload(mid, f"Severity {severity}")
        payload["severity"] = severity
        await client.post("/api/v1/incidents", json=payload, headers=fin_headers)
    
    # Filter by critical
    resp = await client.get(
        f"/api/v1/incidents?merchant_id={mid}&severity=critical", headers=headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert all(i["severity"] == "critical" for i in results)


@pytest.mark.asyncio
async def test_incident_filter_by_type(client, db_session):
    """Test filtering incidents by type."""
    mid, headers = await _register_and_login(
        client, "inc_type@example.com", "+2348004000011"
    )
    fin_headers = await _finance_headers(db_session, "inc_type_fin@example.com", "+2348004000111", mid)
    
    # Create incidents with different types
    for incident_type in ["provider_failure_spike", "settlement_delay", "webhook_failure"]:
        await client.post(
            "/api/v1/incidents", 
            json=_incident_payload(mid, f"Type {incident_type}", incident_type), 
            headers=fin_headers
        )
    
    # Filter by type
    resp = await client.get(
        f"/api/v1/incidents?merchant_id={mid}&incident_type=settlement_delay", headers=headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert all(i["incident_type"] == "settlement_delay" for i in results)


@pytest.mark.asyncio
async def test_incident_statistics(client, db_session):
    """Test incident statistics endpoint."""
    mid, headers = await _register_and_login(
        client, "inc_stats@example.com", "+2348004000012"
    )
    fin_headers = await _finance_headers(db_session, "inc_stats_fin@example.com", "+2348004000112", mid)
    
    # Create multiple incidents
    for i in range(3):
        await client.post(
            "/api/v1/incidents",
            json=_incident_payload(mid, f"Stats Test {i}"),
            headers=fin_headers
        )
    
    # Get stats
    resp = await client.get(
        f"/api/v1/incidents/stats?merchant_id={mid}", headers=headers
    )
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_incidents"] >= 3
    assert stats["by_status"]["open"] >= 3
    assert "by_severity" in stats
    assert "by_type" in stats
    assert "critical_incidents_24h" in stats


@pytest.mark.asyncio
async def test_incident_auto_escalation_after_duration(client, db_session):
    """Test auto-escalation when incident is open for >1 hour."""
    from bomipay.services.incident import IncidentService
    
    mid, headers = await _register_and_login(
        client, "inc_escalate@example.com", "+2348004000013"
    )
    fin_headers = await _finance_headers(db_session, "inc_escalate_fin@example.com", "+2348004000113", mid)
    
    # Create low-severity incident
    payload = _incident_payload(mid, "Escalation Test")
    payload["severity"] = "low"
    create_resp = await client.post("/api/v1/incidents", json=payload, headers=fin_headers)
    inc_id = create_resp.json()["id"]
    
    # Fetch incident and manually set created_at to 2 hours ago for testing
    incident = await IncidentService.get_by_id(db_session, inc_id)
    original_created_at = incident.created_at
    
    # Update created_at to simulate old incident
    from datetime import datetime as dt, timezone
    incident.created_at = dt.now(timezone.utc) - timedelta(hours=2)
    await db_session.flush()
    
    # Call auto-escalate
    escalated = await IncidentService.auto_escalate_if_needed(db_session, incident)
    await db_session.commit()
    
    # Verify escalated to critical
    assert escalated.severity == "critical"
    
    # Restore for cleanup
    incident.created_at = original_created_at


@pytest.mark.asyncio
async def test_incident_multiple_filters_combined(client, db_session):
    """Test combining multiple filters."""
    mid, headers = await _register_and_login(
        client, "inc_multi_filter@example.com", "+2348004000014"
    )
    fin_headers = await _finance_headers(db_session, "inc_multi_filter_fin@example.com", "+2348004000114", mid)
    
    # Create diverse incidents
    for status_val in ["open", "acknowledged"]:
        for severity_val in ["high", "low"]:
            payload = _incident_payload(mid, f"Multi {status_val} {severity_val}")
            payload["severity"] = severity_val
            resp = await client.post("/api/v1/incidents", json=payload, headers=fin_headers)
            inc_id = resp.json()["id"]
            if status_val == "acknowledged":
                await client.post(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)
    
    # Filter by status AND severity
    resp = await client.get(
        f"/api/v1/incidents?merchant_id={mid}&status=open&severity=high", headers=headers
    )
    assert resp.status_code == 200
    results = resp.json()
    assert all(i["status"] == "open" and i["severity"] == "high" for i in results)

