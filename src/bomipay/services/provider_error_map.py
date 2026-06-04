"""Provider error mapping utilities."""
from typing import Tuple


class ProviderErrorMapper:
    """Map provider-specific errors to canonical error codes."""

    @staticmethod
    def map_error(
        provider_name: str,
        http_status: int,
        error_message: str,
    ) -> Tuple[bool, str]:
        """
        Map provider error to retryable flag and error code.

        Returns:
            (is_retryable, error_code)
        """
        if provider_name == "paystack":
            return ProviderErrorMapper._map_paystack_error(http_status, error_message)
        elif provider_name == "flutterwave":
            return ProviderErrorMapper._map_flutterwave_error(http_status, error_message)
        elif provider_name == "monnify":
            return ProviderErrorMapper._map_monnify_error(http_status, error_message)
        else:
            return ProviderErrorMapper._map_generic_error(http_status, error_message)

    @staticmethod
    def _map_paystack_error(http_status: int, error_message: str) -> Tuple[bool, str]:
        """Map Paystack-specific errors."""
        if http_status == 401:
            return (False, "invalid_api_key")
        elif http_status == 403:
            return (False, "insufficient_permissions")
        elif http_status == 404:
            return (False, "resource_not_found")
        elif http_status == 400:
            return (False, "invalid_request")
        elif http_status == 429:
            return (True, "rate_limited")
        elif http_status >= 500:
            return (True, "service_unavailable")
        else:
            return (True, "unknown_error")

    @staticmethod
    def _map_flutterwave_error(http_status: int, error_message: str) -> Tuple[bool, str]:
        """Map Flutterwave-specific errors."""
        if http_status == 401:
            return (False, "invalid_api_key")
        elif http_status == 403:
            return (False, "insufficient_permissions")
        elif http_status == 404:
            return (False, "resource_not_found")
        elif http_status == 400:
            return (False, "invalid_request")
        elif http_status == 429:
            return (True, "rate_limited")
        elif http_status >= 500:
            return (True, "service_unavailable")
        else:
            return (True, "unknown_error")

    @staticmethod
    def _map_monnify_error(http_status: int, error_message: str) -> Tuple[bool, str]:
        """Map Monnify-specific errors."""
        if http_status == 401:
            return (False, "invalid_api_key")
        elif http_status == 403:
            return (False, "insufficient_permissions")
        elif http_status == 404:
            return (False, "resource_not_found")
        elif http_status == 400:
            return (False, "invalid_request")
        elif http_status == 429:
            return (True, "rate_limited")
        elif http_status >= 500:
            return (True, "service_unavailable")
        else:
            return (True, "unknown_error")

    @staticmethod
    def _map_generic_error(http_status: int, error_message: str) -> Tuple[bool, str]:
        """Map generic HTTP errors."""
        if http_status == 401:
            return (False, "unauthorized")
        elif http_status == 403:
            return (False, "forbidden")
        elif http_status == 404:
            return (False, "not_found")
        elif http_status == 400:
            return (False, "bad_request")
        elif http_status == 429:
            return (True, "rate_limited")
        elif http_status >= 500:
            return (True, "service_unavailable")
        else:
            return (True, "unknown_error")
