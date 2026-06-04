"""Staging tests for MonnifyAdapter against a mock HTTP server.

Monnify-specific differences tested here:
- Basic Auth (base64 api_key:secret_key)
- fetch_transactions uses 'content' key and 'hasNext' boolean (not 'data'/'pageCount')
- verify_transaction uses 'data' key
- Zero-based page numbering
- Status values are uppercase (PAID, PENDING, FAILED, COMPLETED)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from bomipay.services.monnify_adapter_new import MonnifyAdapter
from bomipay.services.provider_adapters_async import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

from fixtures.monnify_responses import (
    MONNIFY_INVALID_KEY,
    MONNIFY_LIST_TRANSACTIONS,
    MONNIFY_LIST_TRANSACTIONS_PAGE0,
    MONNIFY_LIST_TRANSACTIONS_PAGE1,
    MONNIFY_RATE_LIMIT_RESPONSE,
    MONNIFY_SERVER_ERROR,
    MONNIFY_VERIFY_COMPLETED,
    MONNIFY_VERIFY_FAILED,
    MONNIFY_VERIFY_PENDING,
    MONNIFY_VERIFY_SUCCESS,
)

VERIFY_URL = "https://api.monnify.com/api/v1/transactions/verify/MNFY%7C20240115103000%7C001"
VERIFY_URL_RAW = "https://api.monnify.com/api/v1/transactions/verify/ref_monnify_001"
LIST_URL = "https://api.monnify.com/api/v1/transactions/search"


@pytest.fixture
def monnify_adapter():
    return MonnifyAdapter(api_key="MK_TEST_staging_key", secret_key="staging_secret")


@pytest.fixture
def date_range():
    return (
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )


@pytest.mark.staging
class TestMonnifyContractVerification:
    """Adapter output must match the canonical transaction schema."""

    async def test_verify_transaction_returns_data_dict(self, monnify_adapter):
        """verify_transaction returns the provider data dict on success."""
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_SUCCESS)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_001")

        assert isinstance(result, dict)

    async def test_verify_transaction_amount_is_integer(self, monnify_adapter):
        """transactionAmount must be an integer."""
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_SUCCESS)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_001")

        assert isinstance(result["transactionAmount"], int)
        assert result["transactionAmount"] == 5000

    async def test_verify_paid_status(self, monnify_adapter):
        """PAID paymentStatus is preserved."""
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_SUCCESS)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_001")

        assert result["paymentStatus"] == "PAID"

    async def test_verify_completed_status(self, monnify_adapter):
        """COMPLETED paymentStatus is preserved."""
        with respx.mock:
            respx.get("https://api.monnify.com/api/v1/transactions/verify/ref_monnify_002").mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_COMPLETED)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_002")

        assert result["paymentStatus"] == "COMPLETED"

    async def test_verify_pending_status(self, monnify_adapter):
        """PENDING paymentStatus is preserved."""
        with respx.mock:
            respx.get("https://api.monnify.com/api/v1/transactions/verify/ref_monnify_003").mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_PENDING)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_003")

        assert result["paymentStatus"] == "PENDING"

    async def test_verify_failed_status(self, monnify_adapter):
        """FAILED paymentStatus is preserved."""
        with respx.mock:
            respx.get("https://api.monnify.com/api/v1/transactions/verify/ref_monnify_004").mock(
                return_value=httpx.Response(200, json=MONNIFY_VERIFY_FAILED)
            )
            result = await monnify_adapter.verify_transaction("ref_monnify_004")

        assert result["paymentStatus"] == "FAILED"

    async def test_fetch_transactions_returns_list(self, monnify_adapter, date_range):
        """fetch_transactions returns a list of content items."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=MONNIFY_LIST_TRANSACTIONS)
            )
            result = await monnify_adapter.fetch_transactions(*date_range)

        assert isinstance(result, list)
        assert len(result) == 3

    async def test_fetch_transactions_each_item_has_integer_amount(self, monnify_adapter, date_range):
        """Every item must have an integer transactionAmount."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=MONNIFY_LIST_TRANSACTIONS)
            )
            result = await monnify_adapter.fetch_transactions(*date_range)

        for txn in result:
            assert isinstance(txn["transactionAmount"], int), (
                f"Non-int transactionAmount: {txn['transactionAmount']}"
            )


@pytest.mark.staging
class TestMonnifyFaultInjection:
    """Adapter must raise the correct exception under fault conditions."""

    async def test_timeout_raises_ProviderTimeoutError(self, monnify_adapter):
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                side_effect=httpx.ReadTimeout("timed out")
            )
            with pytest.raises(ProviderTimeoutError):
                await monnify_adapter.verify_transaction("ref_monnify_001")

    async def test_rate_limit_raises_ProviderRateLimitError(self, monnify_adapter):
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(429, json=MONNIFY_RATE_LIMIT_RESPONSE)
            )
            with pytest.raises(ProviderRateLimitError):
                await monnify_adapter.verify_transaction("ref_monnify_001")

    async def test_server_error_raises_ProviderError(self, monnify_adapter):
        monnify_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(500, json=MONNIFY_SERVER_ERROR)
            )
            with pytest.raises(ProviderError):
                await monnify_adapter.verify_transaction("ref_monnify_001")

    async def test_server_error_is_retryable(self, monnify_adapter):
        monnify_adapter._backoff = AsyncMock(return_value=None)
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(500, json=MONNIFY_SERVER_ERROR)
            )
            with pytest.raises(ProviderError) as exc_info:
                await monnify_adapter.verify_transaction("ref_monnify_001")
        assert exc_info.value.retryable is True

    async def test_invalid_key_raises_ProviderAuthError(self, monnify_adapter):
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(401, json=MONNIFY_INVALID_KEY)
            )
            with pytest.raises(ProviderAuthError):
                await monnify_adapter.verify_transaction("ref_monnify_001")

    async def test_malformed_json_raises_ProviderError(self, monnify_adapter):
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(200, text="<html>Gateway Error</html>")
            )
            with pytest.raises(ProviderError):
                await monnify_adapter.verify_transaction("ref_monnify_001")

    async def test_partial_response_wrong_status_raises_ProviderError(self, monnify_adapter):
        with respx.mock:
            respx.get(VERIFY_URL_RAW).mock(
                return_value=httpx.Response(200, json={"status": True, "data": {}})
            )
            with pytest.raises(ProviderError):
                await monnify_adapter.verify_transaction("ref_monnify_001")


@pytest.mark.staging
class TestMonnifyPagination:
    """Adapter must traverse zero-based multi-page responses correctly."""

    async def test_fetch_transactions_single_page_no_next(self, monnify_adapter, date_range):
        """hasNext=False stops after first page."""
        with respx.mock:
            route = respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json=MONNIFY_LIST_TRANSACTIONS)
            )
            result = await monnify_adapter.fetch_transactions(*date_range)

        assert len(result) == 3
        assert route.call_count == 1

    async def test_fetch_transactions_multi_page_aggregates_all(self, monnify_adapter, date_range):
        """hasNext=True triggers second page fetch; both pages are merged."""
        with respx.mock:
            respx.get(LIST_URL).mock(
                side_effect=[
                    httpx.Response(200, json=MONNIFY_LIST_TRANSACTIONS_PAGE0),
                    httpx.Response(200, json=MONNIFY_LIST_TRANSACTIONS_PAGE1),
                ]
            )
            result = await monnify_adapter.fetch_transactions(*date_range)

        assert len(result) == 2
        refs = [t["transactionReference"] for t in result]
        assert "MNFY|PG|001" in refs
        assert "MNFY|PG|002" in refs

    async def test_fetch_transactions_error_raises_ProviderError(self, monnify_adapter, date_range):
        with respx.mock:
            respx.get(LIST_URL).mock(
                return_value=httpx.Response(200, json={"status": "error", "message": "Not authorised"})
            )
            with pytest.raises(ProviderError):
                await monnify_adapter.fetch_transactions(*date_range)
