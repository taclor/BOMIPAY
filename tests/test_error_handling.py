"""Tests for TASK-001 — Error Handling Hardening.

Test routes are registered on the shared app instance at module import time
using unique /test-errors/* paths that cannot conflict with production routes.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from bomipay.main import app
from bomipay.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    TenantIsolationError,
    ValidationError as BomiValidationError,
    ConflictError,
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    WebhookValidationError,
    DatabaseError,
    IdempotencyConflictError,
)

# ---------------------------------------------------------------------------
# Test-only routes — raise specific exceptions so we can verify HTTP mapping
# ---------------------------------------------------------------------------

@app.get("/test-errors/not-found")
async def _raise_not_found():
    raise NotFoundError(resource="Widget", resource_id="42")


@app.get("/test-errors/permission-denied")
async def _raise_permission_denied():
    raise PermissionDeniedError("You lack the required permissions")


@app.get("/test-errors/tenant-isolation")
async def _raise_tenant_isolation():
    raise TenantIsolationError("Cross-tenant access detected")


@app.get("/test-errors/validation")
async def _raise_validation():
    raise BomiValidationError(field="amount", reason="must be positive")


@app.get("/test-errors/conflict")
async def _raise_conflict():
    raise ConflictError(resource="Transaction")


@app.get("/test-errors/idempotency")
async def _raise_idempotency():
    raise IdempotencyConflictError(idempotency_key="idem-key-123")


@app.get("/test-errors/provider-timeout")
async def _raise_provider_timeout():
    raise ProviderTimeoutError(provider_name="paystack")


@app.get("/test-errors/provider-rate-limit")
async def _raise_provider_rate_limit():
    raise ProviderRateLimitError(provider_name="stripe")


@app.get("/test-errors/provider-retryable")
async def _raise_provider_retryable():
    raise ProviderError(provider_name="flutterwave", retryable=True)


@app.get("/test-errors/provider-non-retryable")
async def _raise_provider_non_retryable():
    raise ProviderError(provider_name="flutterwave", retryable=False)


@app.get("/test-errors/webhook-validation")
async def _raise_webhook_validation():
    raise WebhookValidationError(provider_name="paystack")


@app.get("/test-errors/database-error")
async def _raise_database_error():
    raise DatabaseError("Connection pool exhausted")


@app.get("/test-errors/unhandled")
async def _raise_unhandled():
    raise RuntimeError("Completely unexpected internal failure")


# ---------------------------------------------------------------------------
# Shared fixture — plain AsyncClient (no db override needed for error routes)
# ---------------------------------------------------------------------------

@pytest.fixture
async def error_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_error_shape(data: dict, *, code: str | None = None) -> dict:
    """Assert the standard error envelope is present and return the inner dict."""
    assert "error" in data, f"Missing 'error' key in {data}"
    err = data["error"]
    for field in ("code", "message", "correlation_id", "request_id"):
        assert field in err, f"Missing '{field}' in error envelope: {err}"
    if code:
        assert err["code"] == code, f"Expected code={code!r}, got {err['code']!r}"
    return err


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_not_found_returns_404_with_structured_error(error_client):
    resp = await error_client.get("/test-errors/not-found")
    assert resp.status_code == 404
    err = _assert_error_shape(resp.json(), code="NOT_FOUND")
    assert err["correlation_id"]
    assert err["request_id"]


@pytest.mark.asyncio
async def test_permission_denied_returns_403(error_client):
    resp = await error_client.get("/test-errors/permission-denied")
    assert resp.status_code == 403
    _assert_error_shape(resp.json(), code="PERMISSION_DENIED")


@pytest.mark.asyncio
async def test_tenant_isolation_returns_403(error_client):
    resp = await error_client.get("/test-errors/tenant-isolation")
    assert resp.status_code == 403
    _assert_error_shape(resp.json(), code="TENANT_ISOLATION")


@pytest.mark.asyncio
async def test_validation_error_returns_422(error_client):
    resp = await error_client.get("/test-errors/validation")
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), code="VALIDATION_ERROR")


@pytest.mark.asyncio
async def test_conflict_returns_409(error_client):
    resp = await error_client.get("/test-errors/conflict")
    assert resp.status_code == 409
    _assert_error_shape(resp.json(), code="CONFLICT")


@pytest.mark.asyncio
async def test_idempotency_conflict_returns_409(error_client):
    resp = await error_client.get("/test-errors/idempotency")
    assert resp.status_code == 409
    _assert_error_shape(resp.json(), code="IDEMPOTENCY_CONFLICT")


@pytest.mark.asyncio
async def test_provider_timeout_returns_504(error_client):
    resp = await error_client.get("/test-errors/provider-timeout")
    assert resp.status_code == 504
    _assert_error_shape(resp.json(), code="PROVIDER_TIMEOUT")


@pytest.mark.asyncio
async def test_provider_rate_limit_returns_429(error_client):
    resp = await error_client.get("/test-errors/provider-rate-limit")
    assert resp.status_code == 429
    _assert_error_shape(resp.json(), code="PROVIDER_RATE_LIMITED")


@pytest.mark.asyncio
async def test_provider_retryable_returns_502(error_client):
    resp = await error_client.get("/test-errors/provider-retryable")
    assert resp.status_code == 502
    _assert_error_shape(resp.json(), code="PROVIDER_ERROR")


@pytest.mark.asyncio
async def test_provider_non_retryable_returns_400(error_client):
    resp = await error_client.get("/test-errors/provider-non-retryable")
    assert resp.status_code == 400
    _assert_error_shape(resp.json(), code="PROVIDER_ERROR")


@pytest.mark.asyncio
async def test_webhook_validation_returns_400(error_client):
    resp = await error_client.get("/test-errors/webhook-validation")
    assert resp.status_code == 400
    _assert_error_shape(resp.json(), code="WEBHOOK_VALIDATION_ERROR")


@pytest.mark.asyncio
async def test_database_error_returns_503(error_client):
    resp = await error_client.get("/test-errors/database-error")
    assert resp.status_code == 503
    _assert_error_shape(resp.json(), code="DATABASE_ERROR")


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_without_stack_trace(error_client):
    resp = await error_client.get("/test-errors/unhandled")
    assert resp.status_code == 500
    err = _assert_error_shape(resp.json(), code="INTERNAL_SERVER_ERROR")
    # Must NOT expose internal details / stack traces
    assert "RuntimeError" not in err["message"]
    assert "Traceback" not in err["message"]
    assert err["correlation_id"]


@pytest.mark.asyncio
async def test_correlation_id_request_header_echoed_in_response(error_client):
    """If the caller supplies X-Correlation-ID it must be echoed back."""
    custom_cid = "test-correlation-id-abc123"
    resp = await error_client.get(
        "/test-errors/not-found",
        headers={"X-Correlation-ID": custom_cid},
    )
    assert resp.status_code == 404
    # Header on the response
    assert resp.headers.get("x-correlation-id") == custom_cid
    # Also present inside the error body
    err = resp.json()["error"]
    assert err["correlation_id"] == custom_cid


@pytest.mark.asyncio
async def test_correlation_id_generated_when_not_provided(error_client):
    resp = await error_client.get("/test-errors/not-found")
    assert resp.status_code == 404
    cid_header = resp.headers.get("x-correlation-id")
    assert cid_header  # must be non-empty
    assert resp.json()["error"]["correlation_id"] == cid_header


@pytest.mark.asyncio
async def test_error_response_always_has_required_fields(error_client):
    """Every error route must return the full error envelope."""
    routes = [
        ("/test-errors/not-found", 404),
        ("/test-errors/permission-denied", 403),
        ("/test-errors/tenant-isolation", 403),
        ("/test-errors/validation", 422),
        ("/test-errors/provider-timeout", 504),
        ("/test-errors/provider-rate-limit", 429),
        ("/test-errors/database-error", 503),
        ("/test-errors/unhandled", 500),
    ]
    for path, expected_status in routes:
        resp = await error_client.get(path)
        assert resp.status_code == expected_status, f"Unexpected status for {path}"
        _assert_error_shape(resp.json())


@pytest.mark.asyncio
async def test_x_request_id_header_present_on_error_response(error_client):
    resp = await error_client.get("/test-errors/not-found")
    assert resp.headers.get("x-request-id"), "X-Request-ID must be set on error responses"


@pytest.mark.asyncio
async def test_custom_request_id_echoed(error_client):
    custom_rid = "my-request-id-xyz"
    resp = await error_client.get(
        "/test-errors/not-found",
        headers={"X-Request-ID": custom_rid},
    )
    assert resp.headers.get("x-request-id") == custom_rid
    assert resp.json()["error"]["request_id"] == custom_rid
