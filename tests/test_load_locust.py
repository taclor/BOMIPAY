"""
Locust load test definitions for Bomi Pay.

Run with:
    # Interactive UI (default port 8089)
    locust -f tests/test_load_locust.py --host http://localhost:8000

    # Headless smoke test
    locust -f tests/test_load_locust.py --headless -u 10 -r 2 \\
        --run-time 30s --host http://localhost:8000 \\
        --html load-test-report.html --csv load-test-stats

    # Full load (100 users)
    locust -f tests/test_load_locust.py --headless -u 100 -r 10 \\
        --run-time 60s --host http://localhost:8000 \\
        --html load-test-report.html

NOTE: This file contains class definitions only. It does NOT run during pytest.
"""

import time
import uuid

from locust import HttpUser, between, events, task


# ---------------------------------------------------------------------------
# Event hooks
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def _(environment, **kwargs):
    """Fail the Locust run if error rate exceeds 1%."""
    stats = environment.stats.total
    if stats.num_requests == 0:
        return
    error_rate = stats.num_failures / stats.num_requests
    if error_rate > 0.01:
        environment.process_exit_code = 1


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------

class MerchantDashboardUser(HttpUser):
    """
    Simulates a merchant user navigating the Bomi Pay dashboard.

    Task weights reflect realistic usage patterns:
    - Dashboard views are most frequent (weight 5)
    - Timeline queries are common (weight 4)
    - Incident / transaction browsing (weight 3 each)
    - Provider health checks (weight 2)
    - AI queries are infrequent (weight 1)
    """

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        """Login and store the JWT token + merchant ID for subsequent requests."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "LoadTest123!",
            },
            name="/api/v1/auth/login",
        )
        if response.status_code == 200:
            body = response.json()
            self.token = body.get("access_token", "")
            self.merchant_id = body.get("merchant_id", "test-merchant-id")
        else:
            self.token = ""
            self.merchant_id = "test-merchant-id"

        self.headers = {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(weight=5)
    def get_dashboard(self) -> None:
        self.client.get(
            f"/api/v1/dashboard?merchant_id={self.merchant_id}",
            headers=self.headers,
            name="/api/v1/dashboard",
        )

    @task(weight=4)
    def get_timeline(self) -> None:
        self.client.get(
            f"/api/v1/timeline/payments?merchant_id={self.merchant_id}&limit=20",
            headers=self.headers,
            name="/api/v1/timeline/payments",
        )

    @task(weight=3)
    def get_incidents(self) -> None:
        self.client.get(
            f"/api/v1/incidents?merchant_id={self.merchant_id}&limit=20",
            headers=self.headers,
            name="/api/v1/incidents",
        )

    @task(weight=3)
    def get_transactions(self) -> None:
        self.client.get(
            f"/api/v1/transactions?status=success",
            headers=self.headers,
            name="/api/v1/transactions",
        )

    @task(weight=2)
    def get_provider_health(self) -> None:
        self.client.get(
            f"/api/v1/provider-health/metrics?merchant_id={self.merchant_id}",
            headers=self.headers,
            name="/api/v1/provider-health/metrics",
        )

    @task(weight=2)
    def get_action_center(self) -> None:
        self.client.get(
            f"/api/v1/action-center?merchant_id={self.merchant_id}",
            headers=self.headers,
            name="/api/v1/action-center",
        )

    @task(weight=2)
    def get_dashboard_metrics(self) -> None:
        self.client.get(
            f"/api/v1/dashboard/metrics?merchant_id={self.merchant_id}",
            headers=self.headers,
            name="/api/v1/dashboard/metrics",
        )

    @task(weight=1)
    def ai_query(self) -> None:
        self.client.post(
            "/api/v1/ai-assistant/query",
            json={
                "merchant_id": self.merchant_id,
                "query": "What is the current payment success rate?",
            },
            headers=self.headers,
            name="/api/v1/ai-assistant/query",
        )


class WebhookIngestionUser(HttpUser):
    """
    Simulates rapid webhook ingestion from Paystack.

    Uses a high frequency wait_time (10–50ms) to stress the webhook
    signature-verification and transaction-creation path.
    """

    wait_time = between(0.01, 0.05)

    @task
    def send_paystack_webhook(self) -> None:
        payload = {
            "event": "charge.success",
            "data": {
                "id": int(time.time() * 1000) % 2_000_000_000,
                "reference": f"load_{uuid.uuid4().hex[:12]}",
                "amount": 500_000,   # 5,000 NGN in kobo
                "currency": "NGN",
                "status": "success",
                "channel": "card",
                "gateway_response": "Approved",
                "paid_at": "2024-01-15T10:30:00Z",
                "transaction_date": "2024-01-15T10:30:00Z",
                "customer": {
                    "email": "load@test.com",
                    "phone": "+2348000000001",
                    "first_name": "Load",
                    "last_name": "Test",
                },
                "metadata": {},
            },
        }
        # Signature will be invalid unless PAYSTACK_WEBHOOK_SECRET is configured
        # to match the test value; the test accepts 403 as a non-failure.
        with self.client.post(
            "/webhooks/paystack",
            json=payload,
            headers={"X-Paystack-Signature": "test_signature"},
            name="/webhooks/paystack",
            catch_response=True,
        ) as response:
            # 403 = signature mismatch (expected in envs without real secret)
            # 200 = successfully processed
            if response.status_code in (200, 403):
                response.success()
            else:
                response.failure(
                    f"Unexpected status {response.status_code}: {response.text[:200]}"
                )
