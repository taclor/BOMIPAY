"""Base provider adapter with async HTTP support."""
import abc
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger("bomipay")


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    """Timeout error from provider."""

    def __init__(self, message: str = "Request timeout"):
        super().__init__(message, retryable=True)


class ProviderRateLimitError(ProviderError):
    """Rate limit error from provider."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, retryable=True)


class ProviderAuthError(ProviderError):
    """Authentication error from provider."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, retryable=False)


class BaseAsyncProviderAdapter(abc.ABC):
    """Base class for async provider adapters."""

    provider_name: str
    base_url: str

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        return self.client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> dict:
        """
        Make HTTP request with retry on transient errors.

        Raises:
            ProviderAuthError: On 401/403
            ProviderRateLimitError: On 429
            ProviderTimeoutError: On timeout
            ProviderError: On other errors
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, **kwargs)

                # Handle specific status codes
                if response.status_code == 401:
                    raise ProviderAuthError("Unauthorized - invalid API key")
                elif response.status_code == 403:
                    raise ProviderAuthError("Forbidden - insufficient permissions")
                elif response.status_code == 429:
                    raise ProviderRateLimitError(f"Rate limit exceeded: {response.text}")
                elif response.status_code == 404:
                    raise ProviderError("Resource not found", retryable=False)
                elif response.status_code == 400:
                    raise ProviderError(f"Bad request: {response.text}", retryable=False)
                elif response.status_code >= 500:
                    # Retry on 5xx
                    last_error = ProviderError(
                        f"Server error {response.status_code}: {response.text}",
                        retryable=True,
                    )
                    if attempt < max_retries - 1:
                        await self._backoff(attempt)
                        continue
                    raise last_error
                elif not response.is_success:
                    raise ProviderError(
                        f"HTTP {response.status_code}: {response.text}",
                        retryable=False,
                    )

                return response.json()

            except httpx.TimeoutException as e:
                raise ProviderTimeoutError(str(e))
            except httpx.NetworkError as e:
                last_error = ProviderError(f"Network error: {str(e)}", retryable=True)
                if attempt < max_retries - 1:
                    await self._backoff(attempt)
                    continue
                raise last_error
            except ProviderError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in _request_with_retry: {e}")
                raise ProviderError(str(e), retryable=False)

        if last_error:
            raise last_error

    async def _backoff(self, attempt: int) -> None:
        """Exponential backoff before retry."""
        import asyncio

        backoff_seconds = 2 ** attempt
        await asyncio.sleep(backoff_seconds)

    @abc.abstractmethod
    async def verify_transaction(self, reference: str) -> dict:
        """Verify a transaction by reference."""
        pass

    @abc.abstractmethod
    async def fetch_transactions(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch transactions in date range."""
        pass

    @abc.abstractmethod
    async def fetch_transaction(self, reference: str) -> dict:
        """Fetch single transaction by reference."""
        pass

    @abc.abstractmethod
    async def fetch_settlements(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch settlements in date range."""
        pass

    @abc.abstractmethod
    async def fetch_transfers(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch transfers in date range."""
        pass

    @abc.abstractmethod
    async def fetch_refunds(self, transaction_id: str) -> list[dict]:
        """Fetch refunds for a transaction."""
        pass

    @abc.abstractmethod
    async def get_provider_health(self) -> dict:
        """Get provider health status."""
        pass

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
