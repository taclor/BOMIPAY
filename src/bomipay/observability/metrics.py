"""Prometheus metrics definitions for BomiPay."""
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Isolated registry so tests never conflict with the default global registry.
BOMIPAY_REGISTRY = CollectorRegistry(auto_describe=True)

http_requests_total = Counter(
    "bomipay_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status_code"],
    registry=BOMIPAY_REGISTRY,
)

http_request_duration_seconds = Histogram(
    "bomipay_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    registry=BOMIPAY_REGISTRY,
)

provider_failures_total = Counter(
    "bomipay_provider_failures_total",
    "Total payment-provider failures",
    ["provider_name", "error_type"],
    registry=BOMIPAY_REGISTRY,
)

webhook_processed_total = Counter(
    "bomipay_webhook_processed_total",
    "Total webhooks processed",
    ["provider_name", "status"],
    registry=BOMIPAY_REGISTRY,
)

webhook_processing_duration_seconds = Histogram(
    "bomipay_webhook_processing_duration_seconds",
    "Webhook processing latency in seconds",
    ["provider_name"],
    registry=BOMIPAY_REGISTRY,
)

reconciliation_duration_seconds = Histogram(
    "bomipay_reconciliation_duration_seconds",
    "Reconciliation run duration in seconds",
    registry=BOMIPAY_REGISTRY,
)

incident_count = Gauge(
    "bomipay_incident_count",
    "Current number of open incidents",
    ["merchant_id", "severity", "status"],
    registry=BOMIPAY_REGISTRY,
)

queue_backlog = Gauge(
    "bomipay_queue_backlog",
    "Pending items in async job queues",
    ["queue_name"],
    registry=BOMIPAY_REGISTRY,
)


def get_metrics_output() -> tuple[bytes, str]:
    """Return (body_bytes, content_type) suitable for a /metrics HTTP response."""
    return generate_latest(BOMIPAY_REGISTRY), CONTENT_TYPE_LATEST
