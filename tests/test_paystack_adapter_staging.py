"""Staging tests for PaystackAdapter against a mock HTTP server.

Tests verify:
- Canonical contract (output shape and field types)
- Fault injection (timeout, 429, 500, 401, malformed JSON, partial response)
- Pagination behaviour
"""

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from bomipay.services.paystack_adapter_new import PaystackAdapter
from bomipay.services.provider_adapters_async import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

from fixtures.paystack_responses import (
    PAYSTACK_INVALID_KEY,
    PAYSTACK_LIST_TRANSACTIONS,
    PAYSTACK_LIST_TRANSACTIONS_PAGE1,
    PAYSTACK_LIST_TRANSACTIONS_PAGE2,
    PAYSTACK_RATE_LIMIT_RESPONSE,
    PAYSTACK_SERVER_ERROR,
    PAYSTACK_VERIFY_ABANDONED,
    PAYSTACK_VERIFY_FAILED,
    PAYSTACK_VERIFY_PENDING,
    PAYSTACK_VERIFY_SUCCESS,
)

VERIFY_URL = "https://api.paystack.co/transaction/verify/ref_abc123"
LIST_URL = "https://api.paystack.co/transaction"


@pytest.fixture
def paystack_adapter():
    return PaystackAdapter(api_key="sk_test_staging_key")


@pytest.fixture
def date_range():
    return (
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )


@pytest.mark.staging
class TestPaystackContractVerification:
    """Adapter output must match the canonical transaction schema."""

    async def test_verify_transaction_success_returns_data_dict(self, paystack_adapter):
        """verify_transaction returns the provider data dict on success."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_SUCCESS)
            )
            result = await paystack_adapter.verify_transaction("ref_abc123")

        assert isinstance(result, dict)
        assert result["reference"] == "ref_abc123"
        assert result["id"] == 1234567

    async def test_verify_transaction_amount_is_integer(self, paystack_adapter):
        """Amount returned by provider must be an integer (kobo — no floats)."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_SUCCESS)
            )
            result = await paystack_adapter.verify_transaction("ref_abc123")

        assert isinstance(result["amount"], int)
        assert result["amount"] == 500000

    async def test_verify_transaction_success_status(self, paystack_adapter):
        """Raw 'success' status is preserved in the returned data."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_SUCCESS)
            )
            result = await paystack_adapter.verify_transaction("ref_abc123")

        assert result["status"] == "success"

    async def test_verify_transaction_failed_status(self, paystack_adapter):
        """Failed transaction status is preserved."""
        with respx.mock:
            respx.get("https://api.paystack.co/transaction/verify/ref_failed").mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_FAILED)
            )
            result = await paystack_adapter.verify_transaction("ref_failed")

        assert result["status"] == "failed"
        assert result["amount"] == 200000

    async def test_verify_transaction_abandoned_status(self, paystack_adapter):
        """Abandoned transaction status is preserved in raw output."""
        with respx.mock:
            respx.get("https://api.paystack.co/transaction/verify/ref_abandoned").mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_ABANDONED)
            )
            result = await paystack_adapter.verify_transaction("ref_abandoned")

        assert result["status"] == "abandoned"

    async def test_verify_transaction_pending_status(self, paystack_adapter):
        """Pending transaction status is preserved."""
        with respx.mock:
            respx.get("https://api.paystack.co/transaction/verify/ref_pending").mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_PENDING)
            )
            result = await paystack_adapter.verify_transaction("ref_pending")

        assert result["status"] == "pending"

    async def test_verify_transaction_contains_currency(self, paystack_adapter):
        """Currency field is present in the returned data."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_VERIFY_SUCCESS)
            )
            result = await paystack_adapter.verify_transaction("ref_abc123")

        assert result["currency"] == "NGN"

    async def test_fetch_transactions_returns_list(self, paystack_adapter, date_range):
        """fetch_transactions returns a list."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS)
            )
            result = await paystack_adapter.fetch_transactions(*date_range)

        assert isinstance(result, list)
        assert len(result) == 3

    async def test_fetch_transactions_each_item_has_amount_int(self, paystack_adapter, date_range):
        """Each transaction in the list has an integer amount."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS)
            )
            result = await paystack_adapter.fetch_transactions(*date_range)

        for txn in result:
            assert isinstance(txn["amount"], int), f"amount is {type(txn['amount'])} for {txn}"

    async def test_fetch_transactions_mixed_statuses(self, paystack_adapter, date_range):
        """List response preserves all status values per item."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS)
            )
            result = await paystack_adapter.fetch_transactions(*date_range)

        statuses = {txn["status"] for txn in result}
        assert "success" in statuses
        assert "failed" in statuses
        assert "abandoned" in statuses


@pytest.mark.staging
class TestPaystackFaultInjection:
    """Adapter must raise the correct exception type under fault conditions."""

    async def test_timeout_raises_ProviderTimeoutError(self, paystack_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                side_effect=httpx.ReadTimeout("timed out")
            )
            with pytest.raises(ProviderTimeoutError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_rate_limit_raises_ProviderRateLimitError(self, paystack_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(429, json=PAYSTACK_RATE_LIMIT_RESPONSE)
            )
            with pytest.raises(ProviderRateLimitError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_server_error_raises_ProviderError(self, paystack_adapter):
        paystack_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(500, json=PAYSTACK_SERVER_ERROR)
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_server_error_is_retryable(self, paystack_adapter):
        """500 errors are marked retryable."""
        paystack_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(500, json=PAYSTACK_SERVER_ERROR)
            )
            with pytest.raises(ProviderError) as exc_info:
                await paystack_adapter.verify_transaction("ref_abc123")
        assert exc_info.value.retryable is True

    async def test_invalid_key_raises_ProviderAuthError(self, paystack_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(401, json=PAYSTACK_INVALID_KEY)
            )
            with pytest.raises(ProviderAuthError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_invalid_key_is_not_retryable(self, paystack_adapter):
        """401 errors must NOT be retryable."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(401, json=PAYSTACK_INVALID_KEY)
            )
            with pytest.raises(ProviderAuthError) as exc_info:
                await paystack_adapter.verify_transaction("ref_abc123")
        assert exc_info.value.retryable is False

    async def test_malformed_json_raises_ProviderError(self, paystack_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, text="not json {{{")
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_partial_response_wrong_status_raises_ProviderError(self, paystack_adapter):
        """Response with non-string status triggers ProviderError in adapter."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json={"status": True, "data": {}})
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_network_connection_error_raises_ProviderError(self, paystack_adapter):
        paystack_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.verify_transaction("ref_abc123")

    async def test_resource_not_found_raises_ProviderError(self, paystack_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(404, json={"status": False, "message": "Not found"})
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.verify_transaction("ref_abc123")


@pytest.mark.staging
class TestPaystackPagination:
    """Adapter must correctly traverse multi-page responses."""

    async def test_fetch_transactions_single_page(self, paystack_adapter, date_range):
        """Single page (pageCount=1) makes exactly one request."""
        with respx.mock:
            route = respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS)
            )
            result = await paystack_adapter.fetch_transactions(*date_range)

        assert len(result) == 3
        assert route.call_count == 1

    async def test_fetch_transactions_multi_page_aggregates_all(self, paystack_adapter, date_range):
        """Multi-page response aggregates items from all pages."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                side_effect=[
                    httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS_PAGE1),
                    httpx.Response(200, json=PAYSTACK_LIST_TRANSACTIONS_PAGE2),
                ]
            )
            result = await paystack_adapter.fetch_transactions(*date_range)

        assert len(result) == 2
        refs = [t["reference"] for t in result]
        assert "ref_p1_001" in refs
        assert "ref_p1_002" in refs

    async def test_fetch_transactions_failure_raises_ProviderError(self, paystack_adapter, date_range):
        """Error response on list endpoint raises ProviderError."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json={"status": "error", "message": "Bad request"})
            )
            with pytest.raises(ProviderError):
                await paystack_adapter.fetch_transactions(*date_range)
