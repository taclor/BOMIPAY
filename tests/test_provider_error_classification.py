"""Tests for ProviderErrorMapper and error classification.

Verifies that:
- HTTP status codes are mapped to the correct retryable flag and error code
- All three providers follow the same classification rules
- ProviderError subclasses carry the correct retryable flag
"""

import pytest

from bomipay.services.provider_adapters_async import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from bomipay.services.provider_error_map import ProviderErrorMapper


@pytest.mark.staging
class TestProviderErrorClassification:
    """ProviderErrorMapper must classify HTTP status codes correctly."""

    def test_429_classified_as_retryable(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 429, "Rate limit")
        assert retryable is True
        assert code == "rate_limited"

    def test_500_classified_as_retryable(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 500, "Server error")
        assert retryable is True
        assert code == "service_unavailable"

    def test_503_classified_as_retryable(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 503, "Service unavailable")
        assert retryable is True

    def test_401_classified_as_permanent(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 401, "Invalid key")
        assert retryable is False
        assert code == "invalid_api_key"

    def test_403_classified_as_permanent(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 403, "Forbidden")
        assert retryable is False

    def test_400_classified_as_permanent(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 400, "Bad request")
        assert retryable is False
        assert code == "invalid_request"

    def test_404_classified_as_permanent(self):
        retryable, code = ProviderErrorMapper.map_error("paystack", 404, "Not found")
        assert retryable is False
        assert code == "resource_not_found"

    # --- Exception type retryability ---

    def test_timeout_error_is_retryable(self):
        """ProviderTimeoutError must always be retryable."""
        error = ProviderTimeoutError("Request timed out")
        assert error.retryable is True

    def test_rate_limit_error_is_retryable(self):
        """ProviderRateLimitError must always be retryable."""
        error = ProviderRateLimitError("Too many requests")
        assert error.retryable is True

    def test_auth_error_is_not_retryable(self):
        """ProviderAuthError must never be retryable."""
        error = ProviderAuthError("Unauthorized")
        assert error.retryable is False

    def test_malformed_response_error_is_not_retryable(self):
        """Application-level parse errors must not be retried."""
        error = ProviderError("JSON decode error: ...", retryable=False)
        assert error.retryable is False

    def test_server_error_provider_error_is_retryable(self):
        """5xx errors wrapped in ProviderError must be retryable."""
        error = ProviderError("Server error 500", retryable=True)
        assert error.retryable is True

    # --- Cross-provider consistency ---

    def test_all_providers_429_retryable(self):
        for provider in ("paystack", "flutterwave", "monnify"):
            retryable, _ = ProviderErrorMapper.map_error(provider, 429, "rate limit")
            assert retryable is True, f"{provider}: 429 should be retryable"

    def test_all_providers_401_permanent(self):
        for provider in ("paystack", "flutterwave", "monnify"):
            retryable, _ = ProviderErrorMapper.map_error(provider, 401, "unauthorized")
            assert retryable is False, f"{provider}: 401 should be permanent"

    def test_all_providers_500_retryable(self):
        for provider in ("paystack", "flutterwave", "monnify"):
            retryable, _ = ProviderErrorMapper.map_error(provider, 500, "server error")
            assert retryable is True, f"{provider}: 500 should be retryable"

    def test_all_providers_400_permanent(self):
        for provider in ("paystack", "flutterwave", "monnify"):
            retryable, _ = ProviderErrorMapper.map_error(provider, 400, "bad request")
            assert retryable is False, f"{provider}: 400 should be permanent"

    def test_generic_provider_429_retryable(self):
        retryable, code = ProviderErrorMapper.map_error("unknown_provider", 429, "rate limit")
        assert retryable is True
        assert code == "rate_limited"

    def test_generic_provider_401_permanent(self):
        retryable, code = ProviderErrorMapper.map_error("unknown_provider", 401, "unauthorized")
        assert retryable is False
        assert code == "unauthorized"
