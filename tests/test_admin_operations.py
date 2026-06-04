"""Tests for Admin Operations Console."""
import pytest
from datetime import datetime, timezone, timedelta
import uuid

from bomipay.models.user import Role, User
from bomipay.models.incident import Incident
from bomipay.models.transaction import Transaction
from bomipay.models.transaction_event import TransactionEvent
from bomipay.models.merchant import Merchant
from bomipay.models.provider_account import ProviderAccount
from bomipay.models.audit import AuditLog
from bomipay.models.ai_prompt_version import AIResponseLog
from bomipay.models.reconciliation import ReconciliationRun
from bomipay.services.security import create_access_token
from bomipay.services.user import UserService
from sqlalchemy import select


async def _register_and_login(client, email: str, phone: str, name: str = ""):
    """Register and login a merchant user."""
    merchant_name = name or email.split("@")[0]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Admin Test User",
            "email": email,
            "phone": phone,
            "password": "AdminTest123!",
            "merchant_name": merchant_name,
        },
    )
    assert reg.status_code == 201
    merchant_id = reg.json()["merchant_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AdminTest123!"},
    )
    tokens = login.json()
    return merchant_id, {"Authorization": f"Bearer {tokens['access_token']}"}


async def _admin_headers(db_session, email: str, phone: str) -> dict:
    """Create an admin user and return auth headers."""
    user = await UserService.create_user(
        db_session,
        email=email,
        password="AdminTest123!",
        full_name="Admin User",
        phone=phone,
        role=Role.admin,
        merchant_id=None,
    )
    await db_session.commit()
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}, str(user.id)


# ============================================================================
# Tests: Webhook Management
# ============================================================================

@pytest.mark.asyncio
async def test_replay_webhook_success(client, db_session):
    """Test webhook replay creates new processing entry."""
    admin_headers, admin_id = await _admin_headers(
        db_session, "admin_webhook@example.com", "+2348004000001"
    )
    
    # Create a test transaction and event
    mid = uuid.uuid4()
    tx = Transaction(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="paystack",
        provider_transaction_id="tx_123",
        currency="NGN",
        amount=100000,
        status="pending",
    )
    db_session.add(tx)
    await db_session.flush()
    
    event = TransactionEvent(
        id=uuid.uuid4(),
        transaction_id=tx.id,
        provider_name="paystack",
        provider_event_id="evt_456",
        event_type="charge.success",
        provider_payload={"status": "success"},
    )
    db_session.add(event)
    await db_session.commit()
    
    # Replay the webhook
    resp = await client.post(
        f"/api/v1/admin/webhooks/{event.provider_event_id}/replay",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "replayed"
    assert data["webhook_event_id"] == event.provider_event_id
    assert "job_id" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_replay_webhook_not_found(client, db_session):
    """Test replay webhook returns 404 for non-existent webhook."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_webhook_404@example.com", "+2348004000002"
    )
    
    resp = await client.post(
        f"/api/v1/admin/webhooks/nonexistent_webhook/replay",
        headers=admin_headers,
    )
    
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_webhooks_with_filters(client, db_session):
    """Test listing webhooks with filters."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_list_webhooks@example.com", "+2348004000003"
    )
    
    # Create test events
    mid = uuid.uuid4()
    tx = Transaction(
        id=uuid.uuid4(),
        merchant_id=mid,
        provider_name="paystack",
        provider_transaction_id="tx_789",
        currency="NGN",
        amount=50000,
        status="pending",
    )
    db_session.add(tx)
    await db_session.flush()
    
    event = TransactionEvent(
        id=uuid.uuid4(),
        transaction_id=tx.id,
        provider_name="paystack",
        provider_event_id="evt_789",
        event_type="charge.success",
        provider_payload={"status": "success"},
        status="processed",
    )
    db_session.add(event)
    await db_session.commit()
    
    # List webhooks
    resp = await client.get(
        f"/api/v1/admin/webhooks?provider=paystack&limit=10&offset=0",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "webhooks" in data
    assert "total" in data
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert "correlation_id" in data
    assert len(data["webhooks"]) >= 1


@pytest.mark.asyncio
async def test_webhook_replay_requires_admin_role(client, db_session):
    """Test webhook replay requires admin role."""
    mid, merchant_headers = await _register_and_login(
        client, "merchant_webhook@example.com", "+2348004000004"
    )
    
    resp = await client.post(
        "/api/v1/admin/webhooks/some_webhook/replay",
        headers=merchant_headers,
    )
    
    assert resp.status_code == 403


# ============================================================================
# Tests: Provider Operations
# ============================================================================

@pytest.mark.asyncio
async def test_force_provider_sync(client, db_session):
    """Test forcing immediate provider sync."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_sync@example.com", "+2348004000005"
    )
    
    # Create a test provider account
    merchant = Merchant(
        id=uuid.uuid4(),
        name="Test Merchant",
        email="test_merchant_sync@example.com",
        phone="+2348000000001",
        country="NG",
    )
    db_session.add(merchant)
    await db_session.flush()
    
    provider_account = ProviderAccount(
        id=uuid.uuid4(),
        merchant_id=merchant.id,
        provider_name="paystack",
        api_key_encrypted="encrypted_key",
        secret_encrypted="encrypted_secret",
    )
    db_session.add(provider_account)
    await db_session.commit()
    
    # Force sync
    resp = await client.post(
        f"/api/v1/admin/providers/{provider_account.id}/sync/force?sync_type=transactions",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert "job_id" in data
    assert data["sync_type"] == "transactions"
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_force_provider_sync_not_found(client, db_session):
    """Test force sync returns 404 for non-existent provider."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_sync_404@example.com", "+2348004000006"
    )
    
    resp = await client.post(
        f"/api/v1/admin/providers/nonexistent_provider/sync/force?sync_type=transactions",
        headers=admin_headers,
    )
    
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_provider_health_check(client, db_session):
    """Test provider health check."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_health@example.com", "+2348004000007"
    )
    
    # Create a test provider account
    merchant = Merchant(
        id=uuid.uuid4(),
        name="Test Merchant Health Check",
        email="test_merchant_health@example.com",
        phone="+2348000000002",
        country="NG",
    )
    db_session.add(merchant)
    await db_session.flush()
    
    provider_account = ProviderAccount(
        id=uuid.uuid4(),
        merchant_id=merchant.id,
        provider_name="paystack",
        api_key_encrypted="encrypted_key",
        secret_encrypted="encrypted_secret",
    )
    db_session.add(provider_account)
    await db_session.commit()
    
    # Run health check
    resp = await client.post(
        f"/api/v1/admin/providers/{provider_account.id}/health-check",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "latency_ms" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_provider_health_check_requires_admin(client, db_session):
    """Test health check requires admin role."""
    mid, merchant_headers = await _register_and_login(
        client, "merchant_health@example.com", "+2348004000008"
    )
    
    resp = await client.post(
        f"/api/v1/admin/providers/some_provider/health-check",
        headers=merchant_headers,
    )
    
    assert resp.status_code == 403


# ============================================================================
# Tests: Incident Investigation
# ============================================================================

@pytest.mark.asyncio
async def test_get_incident_timeline(client, db_session):
    """Test getting incident timeline."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_incident@example.com", "+2348004000009"
    )
    
    # Create test incident
    incident = Incident(
        id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        title="Provider Down",
        incident_type="provider_failure_spike",
        severity="high",
        status="open",
        started_at=datetime.now(timezone.utc),
        summary="Test incident",
    )
    db_session.add(incident)
    await db_session.commit()
    
    # Get timeline
    resp = await client.get(
        f"/api/v1/admin/incidents/{incident.id}/timeline",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "incident" in data
    assert data["incident"]["id"] == str(incident.id)
    assert data["incident"]["title"] == "Provider Down"
    assert "related_transactions" in data
    assert "timeline" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_get_incident_timeline_not_found(client, db_session):
    """Test incident timeline returns 404 for non-existent incident."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_incident_404@example.com", "+2348004000010"
    )
    
    resp = await client.get(
        f"/api/v1/admin/incidents/nonexistent_incident/timeline",
        headers=admin_headers,
    )
    
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_incident_related_records(client, db_session):
    """Test getting incident related records."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_related@example.com", "+2348004000011"
    )
    
    # Create test incident
    merchant_id = uuid.uuid4()
    incident = Incident(
        id=uuid.uuid4(),
        merchant_id=merchant_id,
        title="Provider Down",
        incident_type="provider_failure_spike",
        severity="high",
        status="open",
        started_at=datetime.now(timezone.utc),
        summary="Test incident",
    )
    db_session.add(incident)
    await db_session.flush()
    
    # Create related transactions
    for i in range(3):
        tx = Transaction(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            provider_name="paystack",
            provider_transaction_id=f"tx_{i}",
            currency="NGN",
            amount=10000,
            status="pending",
        )
        db_session.add(tx)
    await db_session.commit()
    
    # Get related records
    resp = await client.get(
        f"/api/v1/admin/incidents/{incident.id}/related-records?limit=10&offset=0",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == str(incident.id)
    assert "related_transactions" in data
    assert "total" in data
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert "correlation_id" in data


# ============================================================================
# Tests: Queue/Job Monitoring
# ============================================================================

@pytest.mark.asyncio
async def test_get_queue_status(client, db_session):
    """Test getting queue status."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_queue@example.com", "+2348004000012"
    )
    
    resp = await client.get(
        "/api/v1/admin/queue-status",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "sync_jobs" in data
    assert "webhooks" in data
    assert "ai_tasks" in data
    assert "reconciliation" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_list_failed_jobs(client, db_session):
    """Test listing failed jobs."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_failed@example.com", "+2348004000013"
    )
    
    resp = await client.get(
        "/api/v1/admin/failed-jobs?days=7&limit=10&offset=0",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "failed_jobs" in data
    assert "days" in data
    assert "total" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_retry_failed_job(client, db_session):
    """Test retrying a failed job."""
    admin_headers, admin_id = await _admin_headers(
        db_session, "admin_retry@example.com", "+2348004000014"
    )
    
    job_id = "test_job_123"
    resp = await client.post(
        f"/api/v1/admin/failed-jobs/{job_id}/retry",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "retrying"
    assert data["original_job_id"] == job_id
    assert "new_job_id" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_queue_status_requires_admin(client, db_session):
    """Test queue status requires admin role."""
    mid, merchant_headers = await _register_and_login(
        client, "merchant_queue@example.com", "+2348004000015"
    )
    
    resp = await client.get(
        "/api/v1/admin/queue-status",
        headers=merchant_headers,
    )
    
    assert resp.status_code == 403


# ============================================================================
# Tests: Audit Log
# ============================================================================

@pytest.mark.asyncio
async def test_get_audit_log(client, db_session):
    """Test getting audit log."""
    admin_headers, admin_id = await _admin_headers(
        db_session, "admin_audit@example.com", "+2348004000016"
    )
    
    # Create some audit logs
    audit1 = AuditLog(
        id=uuid.uuid4(),
        actor_id=admin_id,
        actor_role="admin",
        event_type="admin.webhook.replay",
        event_payload={"webhook_id": "test_webhook"},
    )
    audit2 = AuditLog(
        id=uuid.uuid4(),
        actor_id=admin_id,
        actor_role="admin",
        event_type="admin.provider.force_sync",
        event_payload={"provider_id": "test_provider"},
    )
    db_session.add_all([audit1, audit2])
    await db_session.commit()
    
    # Get audit log
    resp = await client.get(
        "/api/v1/admin/audit-log?days=7&limit=20&offset=0",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "audit_logs" in data
    assert "total" in data
    assert data["days"] == 7
    assert "correlation_id" in data
    assert len(data["audit_logs"]) >= 2


@pytest.mark.asyncio
async def test_get_audit_log_with_action_filter(client, db_session):
    """Test getting audit log with action filter."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_audit_filter@example.com", "+2348004000017"
    )
    
    # Get audit log with filter
    resp = await client.get(
        "/api/v1/admin/audit-log?action=webhook&days=7",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "audit_logs" in data
    assert "correlation_id" in data


# ============================================================================
# Tests: Database Inspection
# ============================================================================

@pytest.mark.asyncio
async def test_get_database_stats(client, db_session):
    """Test getting database stats."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_db_stats@example.com", "+2348004000018"
    )
    
    resp = await client.get(
        "/api/v1/admin/db-stats",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "correlation_id" in data
    assert "timestamp" in data
    # Check for expected table stats
    assert "Transaction" in data["stats"]
    assert "Incident" in data["stats"]


@pytest.mark.asyncio
async def test_database_stats_requires_admin(client, db_session):
    """Test database stats requires admin role."""
    mid, merchant_headers = await _register_and_login(
        client, "merchant_db_stats@example.com", "+2348004000019"
    )
    
    resp = await client.get(
        "/api/v1/admin/db-stats",
        headers=merchant_headers,
    )
    
    assert resp.status_code == 403


# ============================================================================
# Tests: AI Response Inspection
# ============================================================================

@pytest.mark.asyncio
async def test_get_ai_response(client, db_session):
    """Test getting AI response details."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_ai@example.com", "+2348004000020"
    )
    
    # Create a test AI response
    ai_response = AIResponseLog(
        id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        prompt_version=1,
        model_name="gpt-4",
        query="What are my recent transactions?",
        context_sources={"transactions": ["tx_1", "tx_2"]},
        response_text="You have 2 recent transactions...",
        confidence_score=9500,
        has_hallucinations=0,
        cited_record_ids=[{"type": "transaction", "id": "tx_1"}],
    )
    db_session.add(ai_response)
    await db_session.commit()
    
    # Get AI response
    resp = await client.get(
        f"/api/v1/admin/ai-responses/{ai_response.id}",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_id"] == str(ai_response.id)
    assert data["query"] == "What are my recent transactions?"
    assert data["model"] == "gpt-4"
    assert data["confidence_score"] == 9500
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_get_ai_response_not_found(client, db_session):
    """Test AI response returns 404 for non-existent response."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_ai_404@example.com", "+2348004000021"
    )
    
    resp = await client.get(
        f"/api/v1/admin/ai-responses/nonexistent_response",
        headers=admin_headers,
    )
    
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_ai_responses_by_query(client, db_session):
    """Test finding AI responses by query pattern."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_ai_query@example.com", "+2348004000022"
    )
    
    # Create test AI responses
    merchant_id = uuid.uuid4()
    for i in range(3):
        ai_response = AIResponseLog(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            prompt_version=1,
            model_name="gpt-4",
            query=f"What are my transactions {i}?",
            context_sources={"transactions": ["tx_1"]},
            response_text="Test response...",
            confidence_score=9000 + i * 100,
            has_hallucinations=0,
            cited_record_ids=[],
        )
        db_session.add(ai_response)
    await db_session.commit()
    
    # Search AI responses
    resp = await client.get(
        "/api/v1/admin/ai-responses-by-query?query=transactions&limit=10&offset=0",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_pattern"] == "transactions"
    assert "responses" in data
    assert "total" in data
    assert "correlation_id" in data
    assert len(data["responses"]) >= 3


@pytest.mark.asyncio
async def test_ai_response_requires_admin(client, db_session):
    """Test AI response inspection requires admin role."""
    mid, merchant_headers = await _register_and_login(
        client, "merchant_ai@example.com", "+2348004000023"
    )
    
    resp = await client.get(
        f"/api/v1/admin/ai-responses/some_response",
        headers=merchant_headers,
    )
    
    assert resp.status_code == 403


# ============================================================================
# Tests: Reconciliation Replay
# ============================================================================

@pytest.mark.asyncio
async def test_replay_reconciliation(client, db_session):
    """Test replaying reconciliation."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_reconcil@example.com", "+2348004000024"
    )
    
    # Create test reconciliation run
    merchant_id = uuid.uuid4()
    run = ReconciliationRun(
        id=uuid.uuid4(),
        merchant_id=merchant_id,
        run_name="Test Reconciliation",
        date_from=datetime.now(timezone.utc) - timedelta(days=1),
        date_to=datetime.now(timezone.utc),
    )
    db_session.add(run)
    await db_session.commit()
    
    # Replay reconciliation
    resp = await client.post(
        f"/api/v1/admin/reconciliation/{run.id}/replay",
        headers=admin_headers,
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "replaying"
    assert data["original_run_id"] == str(run.id)
    assert "new_run_id" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_replay_reconciliation_not_found(client, db_session):
    """Test reconciliation replay returns 404 for non-existent run."""
    admin_headers, _ = await _admin_headers(
        db_session, "admin_reconcil_404@example.com", "+2348004000025"
    )
    
    resp = await client.post(
        f"/api/v1/admin/reconciliation/nonexistent_run/replay",
        headers=admin_headers,
    )
    
    assert resp.status_code == 404
