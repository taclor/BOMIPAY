"""Tests for the observability stack — health endpoints, metrics, and LogContext."""
import json
import logging
import pytest


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_basic(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_live(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client):
    resp = await client.get("/api/v1/health/ready")
    # DB (sqlite) is always available; Redis may not be — either 200 or 503 is valid.
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "db" in data
    assert "redis" in data


@pytest.mark.asyncio
async def test_health_deps(client):
    resp = await client.get("/api/v1/health/deps")
    assert resp.status_code == 200
    data = resp.json()
    assert "db" in data
    assert "redis" in data
    assert "details" in data
    # DB must be reachable (sqlite in-memory test DB)
    assert data["db"] == "ok"


# ---------------------------------------------------------------------------
# Prometheus /metrics endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    # Content-Type must be prometheus text format
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    # At least one bomipay_ metric must be present
    assert "bomipay_" in body


@pytest.mark.asyncio
async def test_metrics_contains_expected_names(client):
    resp = await client.get("/metrics")
    body = resp.text
    for metric_name in [
        "bomipay_http_requests_total",
        "bomipay_http_request_duration_seconds",
        "bomipay_provider_failures_total",
        "bomipay_webhook_processed_total",
        "bomipay_reconciliation_duration_seconds",
        "bomipay_incident_count",
        "bomipay_queue_backlog",
    ]:
        assert metric_name in body, f"Missing metric: {metric_name}"


# ---------------------------------------------------------------------------
# HTTP metrics are recorded after a request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_metrics_increment(client):
    from bomipay.observability.metrics import http_requests_total

    # Hit an endpoint and verify the counter increments
    before = _sum_counter(http_requests_total)
    await client.get("/api/v1/health")
    after = _sum_counter(http_requests_total)
    assert after > before


def _sum_counter(counter) -> float:
    total = 0.0
    for sample in counter.collect()[0].samples:
        if sample.name.endswith("_total"):
            total += sample.value
    return total


# ---------------------------------------------------------------------------
# LogContext
# ---------------------------------------------------------------------------

def test_log_context_binds_and_restores():
    from bomipay.logging import LogContext, _tenant_id_var, _provider_name_var

    # Before context — empty defaults
    assert _tenant_id_var.get() == ""
    assert _provider_name_var.get() == ""

    with LogContext(tenant_id="acme-corp", provider_name="paystack"):
        assert _tenant_id_var.get() == "acme-corp"
        assert _provider_name_var.get() == "paystack"

    # Values restored after exiting context
    assert _tenant_id_var.get() == ""
    assert _provider_name_var.get() == ""


def test_log_context_correlation_and_request_ids():
    from bomipay.logging import LogContext, _correlation_id_var, _request_id_var

    with LogContext(correlation_id="corr-123", request_id="req-456"):
        assert _correlation_id_var.get() == "corr-123"
        assert _request_id_var.get() == "req-456"

    assert _correlation_id_var.get() == ""
    assert _request_id_var.get() == ""


def test_log_context_injects_into_log_record(caplog):
    from bomipay.logging import LogContext, get_logger

    log = get_logger("bomipay.test")
    with LogContext(tenant_id="test-tenant"):
        with caplog.at_level(logging.INFO, logger="bomipay.test"):
            log.info("hello from context")

    # The adapter injects tenant_id into the record's extra dict
    assert any(
        getattr(r, "tenant_id", None) == "test-tenant"
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Sentry and Tracing — smoke tests (no DSN / OTLP endpoint configured)
# ---------------------------------------------------------------------------

def test_setup_sentry_no_dsn():
    """setup_sentry(None) must not raise."""
    from bomipay.observability.sentry import setup_sentry
    setup_sentry(None)  # should be a no-op


def test_setup_tracing_no_endpoint():
    """setup_tracing must not raise when no OTLP endpoint is configured."""
    from bomipay.observability.tracing import setup_tracing
    from fastapi import FastAPI
    dummy_app = FastAPI()
    setup_tracing(dummy_app)  # should complete without error
