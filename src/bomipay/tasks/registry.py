"""Task registry for Celery task discovery and management."""

# Import all tasks so they're registered with Celery
from .provider_sync import (
    sync_provider_transactions,
    sync_provider_settlements,
    sync_provider_transfers,
    sync_provider_refunds,
)
from .webhook_processing import (
    post_process_webhook,
    aggregate_webhook_events,
)
from .reconciliation import (
    run_reconciliation,
    generate_reconciliation_report,
)
from .ai_insight import (
    generate_ai_insight,
    cache_ai_responses,
)
from .incident_generation import detect_and_create_incidents
from .alert_aggregation import (
    aggregate_alerts,
    send_alert_notification,
)
from .provider_health import (
    poll_provider_health,
    calculate_provider_reliability_scores,
)
from .exports import (
    export_transactions_csv,
    export_settlements_csv,
)

TASK_REGISTRY = {
    "sync_provider_transactions": sync_provider_transactions,
    "sync_provider_settlements": sync_provider_settlements,
    "sync_provider_transfers": sync_provider_transfers,
    "sync_provider_refunds": sync_provider_refunds,
    "post_process_webhook": post_process_webhook,
    "aggregate_webhook_events": aggregate_webhook_events,
    "run_reconciliation": run_reconciliation,
    "generate_reconciliation_report": generate_reconciliation_report,
    "generate_ai_insight": generate_ai_insight,
    "cache_ai_responses": cache_ai_responses,
    "detect_and_create_incidents": detect_and_create_incidents,
    "aggregate_alerts": aggregate_alerts,
    "send_alert_notification": send_alert_notification,
    "poll_provider_health": poll_provider_health,
    "calculate_provider_reliability_scores": calculate_provider_reliability_scores,
    "export_transactions_csv": export_transactions_csv,
    "export_settlements_csv": export_settlements_csv,
}

__all__ = [
    "sync_provider_transactions",
    "sync_provider_settlements",
    "sync_provider_transfers",
    "sync_provider_refunds",
    "post_process_webhook",
    "aggregate_webhook_events",
    "run_reconciliation",
    "generate_reconciliation_report",
    "generate_ai_insight",
    "cache_ai_responses",
    "detect_and_create_incidents",
    "aggregate_alerts",
    "send_alert_notification",
    "poll_provider_health",
    "calculate_provider_reliability_scores",
    "export_transactions_csv",
    "export_settlements_csv",
    "TASK_REGISTRY",
]
