"""Tests for Celery async job architecture."""
import pytest
from unittest.mock import patch, MagicMock

from bomipay.services.task_enqueue import TaskEnqueueService
from bomipay.tasks.provider_sync import (
    sync_provider_transactions,
    sync_provider_settlements,
    sync_provider_transfers,
    sync_provider_refunds,
)
from bomipay.tasks.webhook_processing import (
    post_process_webhook,
    aggregate_webhook_events,
)
from bomipay.tasks.reconciliation import (
    run_reconciliation,
    generate_reconciliation_report,
)
from bomipay.tasks.ai_insight import generate_ai_insight, cache_ai_responses
from bomipay.tasks.incident_generation import detect_and_create_incidents
from bomipay.tasks.alert_aggregation import aggregate_alerts, send_alert_notification
from bomipay.tasks.provider_health import (
    poll_provider_health,
    calculate_provider_reliability_scores,
)
from bomipay.tasks.exports import export_transactions_csv, export_settlements_csv


class TestProviderSyncTasks:
    """Test provider sync tasks."""

    def test_sync_provider_transactions(self, celery_app_for_test):
        """Test sync_provider_transactions task execution."""
        result = sync_provider_transactions.apply_async(
            args=("merchant123", "provider_account_456"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"

    def test_sync_provider_settlements(self, celery_app_for_test):
        """Test sync_provider_settlements task execution."""
        result = sync_provider_settlements.apply_async(
            args=("merchant123", "provider_account_456"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"

    def test_sync_provider_transfers(self, celery_app_for_test):
        """Test sync_provider_transfers task execution."""
        result = sync_provider_transfers.apply_async(
            args=("merchant123", "provider_account_456"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"

    def test_sync_provider_refunds(self, celery_app_for_test):
        """Test sync_provider_refunds task execution."""
        result = sync_provider_refunds.apply_async(
            args=("merchant123", "provider_account_456"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"


class TestWebhookProcessingTasks:
    """Test webhook processing tasks."""

    def test_post_process_webhook(self, celery_app_for_test):
        """Test webhook post-processing task execution."""
        result = post_process_webhook.apply_async(
            args=("webhook_event_789",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["webhook_event_id"] == "webhook_event_789"

    def test_aggregate_webhook_events(self, celery_app_for_test):
        """Test webhook event aggregation task execution."""
        result = aggregate_webhook_events.apply_async(
            args=("merchant123",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"


class TestReconciliationTasks:
    """Test reconciliation tasks."""

    def test_run_reconciliation(self, celery_app_for_test):
        """Test reconciliation run task execution."""
        result = run_reconciliation.apply_async(
            args=("merchant123", "2024-01-01", "2024-01-31"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"

    def test_generate_reconciliation_report(self, celery_app_for_test):
        """Test reconciliation report generation task execution."""
        result = generate_reconciliation_report.apply_async(
            args=("reconciliation_run_123",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["reconciliation_run_id"] == "reconciliation_run_123"


class TestAIInsightTasks:
    """Test AI insight tasks."""

    def test_generate_ai_insight(self, celery_app_for_test):
        """Test AI insight generation task execution."""
        result = generate_ai_insight.apply_async(
            args=("merchant123", "money_at_risk"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"
        assert output["insight_type"] == "money_at_risk"

    def test_cache_ai_responses(self, celery_app_for_test):
        """Test AI response caching task execution."""
        result = cache_ai_responses.apply_async(
            args=("merchant123",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"


class TestIncidentDetectionTasks:
    """Test incident detection tasks."""

    def test_detect_and_create_incidents(self, celery_app_for_test):
        """Test incident detection and creation task execution."""
        result = detect_and_create_incidents.apply_async(
            args=("merchant123",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"


class TestAlertAggregationTasks:
    """Test alert aggregation tasks."""

    def test_aggregate_alerts(self, celery_app_for_test):
        """Test alert aggregation task execution."""
        result = aggregate_alerts.apply_async(
            args=("merchant123",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"

    def test_send_alert_notification(self, celery_app_for_test):
        """Test alert notification sending task execution."""
        result = send_alert_notification.apply_async(
            args=("alert_456",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["alert_id"] == "alert_456"


class TestProviderHealthTasks:
    """Test provider health tasks."""

    def test_poll_provider_health(self, celery_app_for_test):
        """Test provider health polling task execution."""
        result = poll_provider_health.apply_async(
            args=("paystack",),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["provider_name"] == "paystack"

    def test_calculate_provider_reliability_scores(self, celery_app_for_test):
        """Test provider reliability score calculation task execution."""
        result = calculate_provider_reliability_scores.apply_async()
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"


class TestExportTasks:
    """Test export tasks."""

    def test_export_transactions_csv(self, celery_app_for_test):
        """Test transaction CSV export task execution."""
        result = export_transactions_csv.apply_async(
            args=("merchant123", "2024-01-01", "2024-01-31"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"
        assert output["merchant_id"] == "merchant123"

    def test_export_settlements_csv(self, celery_app_for_test):
        """Test settlement CSV export task execution."""
        result = export_settlements_csv.apply_async(
            args=("merchant123", "2024-01-01", "2024-01-31"),
        )
        assert result.get() is not None
        output = result.get()
        assert output["status"] == "ok"


class TestTaskEnqueueService:
    """Test TaskEnqueueService helper methods."""

    def test_enqueue_provider_sync(self):
        """Test enqueuing provider sync task."""
        task_id = TaskEnqueueService.enqueue_provider_sync(
            merchant_id="merchant123",
            provider_account_id="provider_account_456",
            sync_type="transactions",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_webhook_post_process(self):
        """Test enqueuing webhook post-processing task."""
        task_id = TaskEnqueueService.enqueue_webhook_post_process(
            webhook_event_id="webhook_event_789",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_reconciliation(self):
        """Test enqueuing reconciliation task."""
        task_id = TaskEnqueueService.enqueue_reconciliation(
            merchant_id="merchant123",
            date_from="2024-01-01",
            date_to="2024-01-31",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_incident_detection(self):
        """Test enqueuing incident detection task."""
        task_id = TaskEnqueueService.enqueue_incident_detection(
            merchant_id="merchant123",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_ai_insight(self):
        """Test enqueuing AI insight task."""
        task_id = TaskEnqueueService.enqueue_ai_insight(
            merchant_id="merchant123",
            insight_type="money_at_risk",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_export_transactions(self):
        """Test enqueuing transaction export task."""
        task_id = TaskEnqueueService.enqueue_export_transactions(
            merchant_id="merchant123",
            date_from="2024-01-01",
            date_to="2024-01-31",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)

    def test_enqueue_export_settlements(self):
        """Test enqueuing settlement export task."""
        task_id = TaskEnqueueService.enqueue_export_settlements(
            merchant_id="merchant123",
            date_from="2024-01-01",
            date_to="2024-01-31",
            countdown=0,
        )
        assert task_id is not None
        assert isinstance(task_id, str)
