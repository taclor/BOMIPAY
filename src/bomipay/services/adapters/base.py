"""Unified provider adapter base — abstract contract + shared HTTP infrastructure."""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

from ..provider_adapters_async import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger("bomipay")

# Re-export exceptions so adapter modules only need one import
__all__ = [
    "AdapterTransaction",
    "AdapterSettlement",
    "ProviderHealthStatus",
    "ProviderAdapter",
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderAuthError",
]


@dataclass
class AdapterTransaction:
    provider_transaction_id: str
    amount_minor: int
    currency: str
    status: str  # pending / success / failed
    reference: str
    raw_payload: dict
    merchant_ref: Optional[str] = None
    fee_minor: Optional[int] = None
    settled_at: Optional[datetime] = None
    metadata: Optional[dict] = None


@dataclass
class AdapterSettlement:
    provider_settlement_id: str
    amount_minor: int
    currency: str
    status: str
    settled_at: Optional[datetime]
    raw_payload: dict


@dataclass
class ProviderHealthStatus:
    is_healthy: bool
    latency_ms: Optional[float]
    success_rate: Optional[float]
    last_checked_at: datetime
    error_message: Optional[str] = None


class ProviderAdapter(ABC):
    """Abstract base for all provider adapters.

    Subclasses get shared HTTP retry / backoff infrastructure for free; they
    only need to implement the eight abstract methods.
    """

    provider_name: str
    base_url: str

    def __init__(self, api_key: str, secret_key: Optional[str] = None, timeout: int = 30):
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # HTTP infrastructure
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> dict:
        """Make an HTTP request with exponential-backoff retry on transient errors.

        Raises:
            ProviderAuthError: 401 / 403
            ProviderRateLimitError: 429
            ProviderTimeoutError: network timeout
            ProviderError: all other failures
        """
        client = await self._get_client()
        last_error: Optional[ProviderError] = None

        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, **kwargs)

                if response.status_code == 401:
                    raise ProviderAuthError("Unauthorized - invalid API key")
                if response.status_code == 403:
                    raise ProviderAuthError("Forbidden - insufficient permissions")
                if response.status_code == 429:
                    raise ProviderRateLimitError(f"Rate limit exceeded: {response.text}")
                if response.status_code == 404:
                    raise ProviderError("Resource not found", retryable=False)
                if response.status_code == 400:
                    raise ProviderError(f"Bad request: {response.text}", retryable=False)
                if response.status_code >= 500:
                    last_error = ProviderError(
                        f"Server error {response.status_code}: {response.text}",
                        retryable=True,
                    )
                    if attempt < max_retries - 1:
                        await self._backoff(attempt)
                        continue
                    raise last_error
                if not response.is_success:
                    raise ProviderError(
                        f"HTTP {response.status_code}: {response.text}",
                        retryable=False,
                    )

                return response.json()

            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(str(exc))
            except httpx.NetworkError as exc:
                last_error = ProviderError(f"Network error: {exc}", retryable=True)
                if attempt < max_retries - 1:
                    await self._backoff(attempt)
                    continue
                raise last_error
            except ProviderError:
                raise
            except Exception as exc:
                logger.error("Unexpected error in _request_with_retry: %s", exc)
                raise ProviderError(str(exc), retryable=False)

        if last_error:
            raise last_error

    async def _backoff(self, attempt: int) -> None:
        """Exponential backoff: 2^attempt seconds (capped at 30 s)."""
        await asyncio.sleep(min(2 ** attempt, 30))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ProviderAdapter":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Abstract contract
    # ------------------------------------------------------------------

    @abstractmethod
    async def verify_transaction(self, reference: str) -> AdapterTransaction: ...

    @abstractmethod
    async def fetch_transaction(self, provider_id: str) -> AdapterTransaction: ...

    @abstractmethod
    async def fetch_transactions(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[AdapterTransaction]: ...

    @abstractmethod
    async def fetch_settlements(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[AdapterSettlement]: ...

    @abstractmethod
    async def fetch_transfers(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]: ...

    @abstractmethod
    async def fetch_refunds(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_provider_health(self) -> ProviderHealthStatus: ...

    @abstractmethod
    async def process_webhook(self, payload: dict, signature: str) -> dict: ...
