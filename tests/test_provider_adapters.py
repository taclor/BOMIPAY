"""Tests for provider adapters and normalization."""
import asyncio
import base64
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

from bomipay.services.provider_adapters_async import (
    BaseAsyncProviderAdapter,
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthError,
)
from bomipay.services.paystack_adapter_new import PaystackAdapter
from bomipay.services.flutterwave_adapter_new import FlutterwaveAdapter
from bomipay.services.monnify_adapter_new import MonnifyAdapter
from bomipay.services.provider_error_map import ProviderErrorMapper
from bomipay.services.provider_normalize import ProviderNormalizer


class TestProviderErrors:
    """Test provider error handling."""

    def test_provider_error_retryable(self):
        """Test ProviderError with retryable flag."""
        error = ProviderError("Test error", retryable=True)
        assert error.retryable is True
        assert error.message == "Test error"

    def test_provider_timeout_error(self):
        """Test ProviderTimeoutError is retryable."""
        error = ProviderTimeoutError()
        assert error.retryable is True

    def test_provider_rate_limit_error(self):
        """Test ProviderRateLimitError is retryable."""
        error = ProviderRateLimitError()
        assert error.retryable is True

    def test_provider_auth_error(self):
        """Test ProviderAuthError is not retryable."""
        error = ProviderAuthError()
        assert error.retryable is False


class TestPaystackAdapter:
    """Test Paystack adapter."""

    @pytest.mark.asyncio
    async def test_verify_transaction_success(self):
        """Test successful transaction verification."""
        adapter = PaystackAdapter(api_key="test_key")

        mock_response = {
            "status": "success",
            "data": {
                "id": 12345,
                "reference": "ref_123",
                "amount": 50000,
                "currency": "NGN",
                "status": "success",
                "created_at": "2024-01-01T12:00:00Z",
            },
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await adapter.verify_transaction("ref_123")

            assert result["id"] == 12345
            assert result["reference"] == "ref_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_transaction_failure(self):
        """Test transaction verification failure."""
        adapter = PaystackAdapter(api_key="test_key")

        mock_response = {
            "status": "error",
            "message": "Transaction not found",
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(ProviderError):
                await adapter.verify_transaction("invalid_ref")

    @pytest.mark.asyncio
    async def test_fetch_transactions_pagination(self):
        """Test fetching transactions with pagination."""
        adapter = PaystackAdapter(api_key="test_key")
        date_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

        mock_response_page1 = {
            "status": "success",
            "data": [
                {"id": 1, "reference": "ref_1", "amount": 50000},
                {"id": 2, "reference": "ref_2", "amount": 60000},
            ],
            "meta": {"pageCount": 2},
        }

        mock_response_page2 = {
            "status": "success",
            "data": [
                {"id": 3, "reference": "ref_3", "amount": 70000},
            ],
            "meta": {"pageCount": 2},
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [mock_response_page1, mock_response_page2]

            result = await adapter.fetch_transactions(date_from, date_to)

            assert len(result) == 3
            assert result[0]["id"] == 1
            assert result[2]["id"] == 3
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_provider_health_ok(self):
        """Test provider health check."""
        adapter = PaystackAdapter(api_key="test_key")

        mock_response = {
            "status": "success",
            "data": [{"id": 1, "name": "Bank Name"}],
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await adapter.get_provider_health()

            assert result["status"] == "ok"
            assert "latency_ms" in result
            assert "timestamp" in result


class TestFlutterwaveAdapter:
    """Test Flutterwave adapter."""

    @pytest.mark.asyncio
    async def test_verify_transaction_success(self):
        """Test successful Flutterwave transaction verification."""
        adapter = FlutterwaveAdapter(api_key="test_key")

        mock_response = {
            "status": "success",
            "data": {
                "id": 12345,
                "flw_ref": "ref_123",
                "amount": 50000,
                "currency": "NGN",
                "status": "successful",
                "created_at": "2024-01-01T12:00:00Z",
            },
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await adapter.verify_transaction("ref_123")

            assert result["id"] == 12345
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_transactions_pagination(self):
        """Test fetching Flutterwave transactions with pagination."""
        adapter = FlutterwaveAdapter(api_key="test_key")
        date_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

        mock_response_page1 = {
            "status": "success",
            "data": [
                {"id": 1, "flw_ref": "ref_1", "amount": 50000},
                {"id": 2, "flw_ref": "ref_2", "amount": 60000},
            ],
            "meta": {"pagination": {"has_more": True}},
        }

        mock_response_page2 = {
            "status": "success",
            "data": [
                {"id": 3, "flw_ref": "ref_3", "amount": 70000},
            ],
            "meta": {"pagination": {"has_more": False}},
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [mock_response_page1, mock_response_page2]

            result = await adapter.fetch_transactions(date_from, date_to)

            assert len(result) == 3
            assert result[0]["id"] == 1


class TestMonnifyAdapter:
    """Test Monnify adapter."""

    def test_adapter_initialization(self):
        """Test Monnify adapter initialization with Basic Auth."""
        adapter = MonnifyAdapter(api_key="test_key", secret_key="test_secret")

        # Check that Basic Auth header is correctly formatted
        expected_credentials = base64.b64encode(b"test_key:test_secret").decode()
        assert adapter.headers["Authorization"] == f"Basic {expected_credentials}"

    @pytest.mark.asyncio
    async def test_verify_transaction_success(self):
        """Test successful Monnify transaction verification."""
        adapter = MonnifyAdapter(api_key="test_key", secret_key="test_secret")

        mock_response = {
            "status": "success",
            "data": {
                "transactionReference": "ref_123",
                "transactionAmount": 50000,
                "currency": "NGN",
                "paymentStatus": "PAID",
                "createdOn": "2024-01-01T12:00:00Z",
            },
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await adapter.verify_transaction("ref_123")

            assert result["transactionReference"] == "ref_123"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_transactions_pagination(self):
        """Test fetching Monnify transactions with pagination."""
        adapter = MonnifyAdapter(api_key="test_key", secret_key="test_secret")
        date_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

        mock_response_page1 = {
            "status": "success",
            "content": [
                {"transactionReference": "ref_1", "transactionAmount": 50000},
                {"transactionReference": "ref_2", "transactionAmount": 60000},
            ],
            "hasNext": True,
        }

        mock_response_page2 = {
            "status": "success",
            "content": [
                {"transactionReference": "ref_3", "transactionAmount": 70000},
            ],
            "hasNext": False,
        }

        with patch.object(
            adapter, "_request_with_retry", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [mock_response_page1, mock_response_page2]

            result = await adapter.fetch_transactions(date_from, date_to)

            assert len(result) == 3
            assert result[0]["transactionReference"] == "ref_1"


class TestProviderErrorMapper:
    """Test provider error mapping."""

    def test_paystack_auth_error(self):
        """Test Paystack 401 error mapping."""
        is_retryable, code = ProviderErrorMapper.map_error("paystack", 401, "Unauthorized")
        assert is_retryable is False
        assert code == "invalid_api_key"

    def test_paystack_rate_limit(self):
        """Test Paystack 429 error mapping."""
        is_retryable, code = ProviderErrorMapper.map_error("paystack", 429, "Rate limited")
        assert is_retryable is True
        assert code == "rate_limited"

    def test_paystack_server_error(self):
        """Test Paystack 500 error mapping."""
        is_retryable, code = ProviderErrorMapper.map_error("paystack", 500, "Server error")
        assert is_retryable is True
        assert code == "service_unavailable"

    def test_flutterwave_auth_error(self):
        """Test Flutterwave 401 error mapping."""
        is_retryable, code = ProviderErrorMapper.map_error("flutterwave", 401, "Unauthorized")
        assert is_retryable is False
        assert code == "invalid_api_key"

    def test_monnify_rate_limit(self):
        """Test Monnify 429 error mapping."""
        is_retryable, code = ProviderErrorMapper.map_error("monnify", 429, "Rate limited")
        assert is_retryable is True
        assert code == "rate_limited"


class TestProviderNormalizer:
    """Test provider response normalization."""

    def test_normalize_paystack_transaction(self):
        """Test Paystack transaction normalization."""
        raw_txn = {
            "id": 12345,
            "reference": "ref_123",
            "amount": 50000,
            "currency": "NGN",
            "status": "success",
            "created_at": "2024-01-01T12:00:00Z",
            "customer": {"email": "customer@example.com"},
            "metadata": {"order_id": "order_1"},
        }

        result = ProviderNormalizer.normalize_transaction("paystack", raw_txn)

        assert result["provider_transaction_id"] == "12345"
        assert result["amount"] == 50000
        assert result["currency"] == "NGN"
        assert result["status"] == "success"
        assert result["customer_email"] == "customer@example.com"
        assert result["metadata"] == {"order_id": "order_1"}

    def test_normalize_flutterwave_transaction(self):
        """Test Flutterwave transaction normalization."""
        raw_txn = {
            "id": 12345,
            "flw_ref": "ref_123",
            "amount": 50000,
            "currency": "NGN",
            "status": "successful",
            "created_at": "2024-01-01T12:00:00Z",
            "customer": {"email": "customer@example.com"},
            "meta": {"order_id": "order_1"},
        }

        result = ProviderNormalizer.normalize_transaction("flutterwave", raw_txn)

        assert result["provider_transaction_id"] == "12345"
        assert result["amount"] == 50000
        assert result["status"] == "success"

    def test_normalize_monnify_transaction(self):
        """Test Monnify transaction normalization."""
        raw_txn = {
            "transactionReference": "ref_123",
            "transactionAmount": 50000,
            "currency": "NGN",
            "paymentStatus": "PAID",
            "createdOn": "2024-01-01T12:00:00Z",
            "customerEmail": "customer@example.com",
            "metadata": {"order_id": "order_1"},
        }

        result = ProviderNormalizer.normalize_transaction("monnify", raw_txn)

        assert result["provider_transaction_id"] == "ref_123"
        assert result["amount"] == 50000
        assert result["status"] == "success"

    def test_normalize_settlement(self):
        """Test settlement normalization."""
        raw_settlement = {
            "id": 456,
            "reference": "settle_123",
            "amount": 100000,
            "currency": "NGN",
            "status": "completed",
            "created_at": "2024-01-05T12:00:00Z",
        }

        result = ProviderNormalizer.normalize_settlement("paystack", raw_settlement)

        assert result["provider_settlement_id"] == "456"
        assert result["amount"] == 100000
        assert result["status"] == "success"

    def test_normalize_transfer(self):
        """Test transfer normalization."""
        raw_transfer = {
            "id": 789,
            "reference": "transfer_123",
            "amount": 75000,
            "currency": "NGN",
            "status": "completed",
            "created_at": "2024-01-10T12:00:00Z",
        }

        result = ProviderNormalizer.normalize_transfer("paystack", raw_transfer)

        assert result["provider_transfer_id"] == "789"
        assert result["amount"] == 75000

    def test_normalize_refund(self):
        """Test refund normalization."""
        raw_refund = {
            "id": 999,
            "reference": "refund_123",
            "amount": 25000,
            "currency": "NGN",
            "status": "completed",
            "created_at": "2024-01-15T12:00:00Z",
        }

        result = ProviderNormalizer.normalize_refund("paystack", raw_refund)

        assert result["provider_refund_id"] == "999"
        assert result["amount"] == 25000

    def test_parse_iso_datetime(self):
        """Test ISO datetime parsing."""
        # ISO format with Z
        result = ProviderNormalizer._parse_iso_datetime("2024-01-01T12:00:00Z")
        assert isinstance(result, datetime)

        # ISO format with timezone
        result = ProviderNormalizer._parse_iso_datetime("2024-01-01T12:00:00+00:00")
        assert isinstance(result, datetime)

        # None input
        result = ProviderNormalizer._parse_iso_datetime(None)
        assert result is None

        # Already datetime
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = ProviderNormalizer._parse_iso_datetime(dt)
        assert result == dt


class TestProviderAdapterIntegration:
    """Integration tests for provider adapters."""

    @pytest.mark.asyncio
    async def test_paystack_auth_error_handling(self):
        """Test Paystack adapter handles 401 errors correctly."""
        adapter = PaystackAdapter(api_key="invalid_key")

        with patch.object(
            adapter, "_request_with_retry", side_effect=ProviderAuthError()
        ) as mock_request:
            with pytest.raises(ProviderAuthError):
                await adapter.verify_transaction("ref_123")

    @pytest.mark.asyncio
    async def test_flutterwave_timeout_handling(self):
        """Test Flutterwave adapter handles timeouts correctly."""
        adapter = FlutterwaveAdapter(api_key="test_key")

        with patch.object(
            adapter, "_request_with_retry", side_effect=ProviderTimeoutError()
        ):
            result = await adapter.get_provider_health()

            assert result["status"] == "down"
            assert result["error"] == "Timeout"

    @pytest.mark.asyncio
    async def test_monnify_rate_limit_handling(self):
        """Test Monnify adapter handles rate limiting correctly."""
        adapter = MonnifyAdapter(api_key="test_key", secret_key="test_secret")

        with patch.object(
            adapter, "_request_with_retry", side_effect=ProviderRateLimitError()
        ):
            result = await adapter.get_provider_health()

            assert result["status"] == "degraded"
            assert "Rate limit" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
