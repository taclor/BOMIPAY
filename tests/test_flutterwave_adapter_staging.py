"""Staging tests for FlutterwaveAdapter against a mock HTTP server.

Tests verify:
- Canonical contract (output shape and field types)
- Fault injection (timeout, 429, 500, 401, malformed JSON)
- Pagination behaviour
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from bomipay.services.flutterwave_adapter_new import FlutterwaveAdapter
from bomipay.services.provider_adapters_async import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

from fixtures.flutterwave_responses import (
    FLW_INVALID_KEY,
    FLW_LIST_TRANSACTIONS,
    FLW_LIST_TRANSACTIONS_PAGE1,
    FLW_LIST_TRANSACTIONS_PAGE2,
    FLW_RATE_LIMIT_RESPONSE,
    FLW_SERVER_ERROR,
    FLW_VERIFY_FAILED,
    FLW_VERIFY_PENDING,
    FLW_VERIFY_SUCCESS,
)

VERIFY_URL = "https://api.flutterwave.com/v3/transactions/flw_ref_abc123/verify"
LIST_URL = "https://api.flutterwave.com/v3/transactions"


@pytest.fixture
def flw_adapter():
    return FlutterwaveAdapter(api_key="FLWSECK_TEST-staging-key")


@pytest.fixture
def date_range():
    return (
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )


@pytest.mark.staging
class TestFlutterwaveContractVerification:
    """Adapter output must match the canonical transaction schema."""

    async def test_verify_transaction_returns_data_dict(self, flw_adapter):
        """verify_transaction returns the provider data dict on success."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_SUCCESS)
            )
            result = await flw_adapter.verify_transaction("flw_ref_abc123")

        assert isinstance(result, dict)
        assert result["tx_ref"] == "flw_ref_abc123"

    async def test_verify_transaction_amount_is_integer(self, flw_adapter):
        """Amount must be coercible to int (Flutterwave returns major units)."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_SUCCESS)
            )
            result = await flw_adapter.verify_transaction("flw_ref_abc123")

        assert isinstance(result["amount"], int)
        assert result["amount"] == 5000

    async def test_verify_transaction_success_status(self, flw_adapter):
        """'successful' status is preserved in returned data."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_SUCCESS)
            )
            result = await flw_adapter.verify_transaction("flw_ref_abc123")

        assert result["status"] == "successful"

    async def test_verify_transaction_failed_status(self, flw_adapter):
        """Failed transaction status is preserved."""
        with respx.mock:
            respx.get("https://api.flutterwave.com/v3/transactions/flw_ref_failed/verify").mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_FAILED)
            )
            result = await flw_adapter.verify_transaction("flw_ref_failed")

        assert result["status"] == "failed"

    async def test_verify_transaction_pending_status(self, flw_adapter):
        """Pending status is preserved."""
        with respx.mock:
            respx.get("https://api.flutterwave.com/v3/transactions/flw_ref_pending/verify").mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_PENDING)
            )
            result = await flw_adapter.verify_transaction("flw_ref_pending")

        assert result["status"] == "pending"

    async def test_verify_transaction_contains_currency(self, flw_adapter):
        """Currency field is present."""
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json=FLW_VERIFY_SUCCESS)
            )
            result = await flw_adapter.verify_transaction("flw_ref_abc123")

        assert result["currency"] == "NGN"

    async def test_fetch_transactions_returns_list(self, flw_adapter, date_range):
        """fetch_transactions returns a list."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=FLW_LIST_TRANSACTIONS)
            )
            result = await flw_adapter.fetch_transactions(*date_range)

        assert isinstance(result, list)
        assert len(result) == 3

    async def test_fetch_transactions_each_item_has_integer_amount(self, flw_adapter, date_range):
        """Every item in the fetched list has an integer amount."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=FLW_LIST_TRANSACTIONS)
            )
            result = await flw_adapter.fetch_transactions(*date_range)

        for txn in result:
            assert isinstance(txn["amount"], int), f"Non-int amount: {txn['amount']}"


@pytest.mark.staging
class TestFlutterwaveFaultInjection:
    """Adapter must raise the correct exception under fault conditions."""

    async def test_timeout_raises_ProviderTimeoutError(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                side_effect=httpx.ReadTimeout("timed out")
            )
            with pytest.raises(ProviderTimeoutError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_rate_limit_raises_ProviderRateLimitError(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(429, json=FLW_RATE_LIMIT_RESPONSE)
            )
            with pytest.raises(ProviderRateLimitError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_server_error_raises_ProviderError(self, flw_adapter):
        flw_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(500, json=FLW_SERVER_ERROR)
            )
            with pytest.raises(ProviderError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_server_error_is_retryable(self, flw_adapter):
        flw_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(500, json=FLW_SERVER_ERROR)
            )
            with pytest.raises(ProviderError) as exc_info:
                await flw_adapter.verify_transaction("flw_ref_abc123")
        assert exc_info.value.retryable is True

    async def test_invalid_key_raises_ProviderAuthError(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(401, json=FLW_INVALID_KEY)
            )
            with pytest.raises(ProviderAuthError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_invalid_key_is_not_retryable(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(401, json=FLW_INVALID_KEY)
            )
            with pytest.raises(ProviderAuthError) as exc_info:
                await flw_adapter.verify_transaction("flw_ref_abc123")
        assert exc_info.value.retryable is False

    async def test_malformed_json_raises_ProviderError(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, text="not json {{")
            )
            with pytest.raises(ProviderError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_partial_response_wrong_status_raises_ProviderError(self, flw_adapter):
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                return_value=httpx.Response(200, json={"status": True, "data": {}})
            )
            with pytest.raises(ProviderError):
                await flw_adapter.verify_transaction("flw_ref_abc123")

    async def test_network_error_raises_ProviderError(self, flw_adapter):
        flw_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL).mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            with pytest.raises(ProviderError):
                await flw_adapter.verify_transaction("flw_ref_abc123")


@pytest.mark.staging
class TestFlutterwavePagination:
    """Adapter must traverse multi-page responses correctly."""

    async def test_fetch_transactions_single_page_no_more(self, flw_adapter, date_range):
        """has_more=False stops after the first page."""
        with respx.mock:
            route = respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=FLW_LIST_TRANSACTIONS)
            )
            result = await flw_adapter.fetch_transactions(*date_range)

        assert len(result) == 3
        assert route.call_count == 1

    async def test_fetch_transactions_multi_page_aggregates_all(self, flw_adapter, date_range):
        """Two pages are fetched and merged when has_more=True on first page."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                side_effect=[
                    httpx.Response(200, json=FLW_LIST_TRANSACTIONS_PAGE1),
                    httpx.Response(200, json=FLW_LIST_TRANSACTIONS_PAGE2),
                ]
            )
            result = await flw_adapter.fetch_transactions(*date_range)

        assert len(result) == 2
        refs = [t["tx_ref"] for t in result]
        assert "flw_p1_001" in refs
        assert "flw_p1_002" in refs

    async def test_fetch_transactions_error_raises_ProviderError(self, flw_adapter, date_range):
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json={"status": "error", "message": "Unauthorized"})
            )
            with pytest.raises(ProviderError):
                await flw_adapter.fetch_transactions(*date_range)
