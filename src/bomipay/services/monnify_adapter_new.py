# DEPRECATED: Use src.bomipay.services.adapters instead
# This module is kept for backwards compatibility; new code should import from
# bomipay.services.adapters (e.g. ``from bomipay.services.adapters import get_adapter``).
"""Monnify provider adapter."""
import base64
import logging
from datetime import datetime
from typing import Any

from .provider_adapters_async import BaseAsyncProviderAdapter, ProviderError, ProviderTimeoutError

logger = logging.getLogger("bomipay")


class MonnifyAdapter(BaseAsyncProviderAdapter):
    """Monnify payment provider adapter."""

    provider_name = "monnify"
    base_url = "https://api.monnify.com"

    def __init__(self, api_key: str, secret_key: str = "", timeout: int = 30):
        super().__init__(api_key, timeout)
        self.secret_key = secret_key
        # Monnify uses Basic Auth: base64(api_key:secret_key)
        credentials = f"{api_key}:{secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.headers = {"Authorization": f"Basic {encoded}"}

    async def verify_transaction(self, reference: str) -> dict:
        """Verify transaction by reference."""
        url = f"{self.base_url}/api/v1/transactions/verify/{reference}"
        response = await self._request_with_retry("GET", url, headers=self.headers)

        if response.get("status") != "success":
            raise ProviderError(
                f"Failed to verify transaction: {response.get('message')}",
                retryable=False,
            )

        return response.get("data", {})

    async def fetch_transactions(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch transactions in date range with pagination."""
        transactions = []
        page = 0
        size = 100

        while True:
            url = f"{self.base_url}/api/v1/transactions/search"
            params = {
                "pageNo": page,
                "pageSize": size,
                "startDate": date_from.isoformat(),
                "endDate": date_to.isoformat(),
            }

            response = await self._request_with_retry(
                "GET",
                url,
                headers=self.headers,
                params=params,
            )

            if response.get("status") != "success":
                raise ProviderError(
                    f"Failed to fetch transactions: {response.get('message')}",
                    retryable=False,
                )

            content = response.get("content", [])
            transactions.extend(content)

            # Check if there are more pages
            if not response.get("hasNext", False):
                break

            page += 1

        return transactions

    async def fetch_transaction(self, reference: str) -> dict:
        """Fetch single transaction by reference."""
        return await self.verify_transaction(reference)

    async def fetch_settlements(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch settlements in date range with pagination."""
        settlements = []
        page = 0
        size = 100

        while True:
            url = f"{self.base_url}/api/v1/settlements"
            params = {
                "pageNo": page,
                "pageSize": size,
                "startDate": date_from.isoformat(),
                "endDate": date_to.isoformat(),
            }

            try:
                response = await self._request_with_retry(
                    "GET",
                    url,
                    headers=self.headers,
                    params=params,
                )

                if response.get("status") != "success":
                    logger.warning(
                        f"Failed to fetch settlements: {response.get('message')}"
                    )
                    break

                content = response.get("content", [])
                settlements.extend(content)

                # Check if there are more pages
                if not response.get("hasNext", False):
                    break

                page += 1

            except ProviderError as e:
                if not e.retryable:
                    logger.debug(f"Settlements not available: {e}")
                    break
                raise

        return settlements

    async def fetch_transfers(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Fetch transfers in date range with pagination."""
        transfers = []
        page = 0
        size = 100

        while True:
            url = f"{self.base_url}/api/v1/transfers"
            params = {
                "pageNo": page,
                "pageSize": size,
                "startDate": date_from.isoformat(),
                "endDate": date_to.isoformat(),
            }

            try:
                response = await self._request_with_retry(
                    "GET",
                    url,
                    headers=self.headers,
                    params=params,
                )

                if response.get("status") != "success":
                    logger.warning(f"Failed to fetch transfers: {response.get('message')}")
                    break

                content = response.get("content", [])

                # Filter by date range
                for item in content:
                    created_on = item.get("createdOn")
                    if created_on:
                        try:
                            item_date = datetime.fromisoformat(
                                created_on.replace("Z", "+00:00")
                            )
                            if date_from <= item_date <= date_to:
                                transfers.append(item)
                        except (ValueError, AttributeError):
                            transfers.append(item)
                    else:
                        transfers.append(item)

                # Check if there are more pages
                if not response.get("hasNext", False):
                    break

                page += 1

            except ProviderError as e:
                if not e.retryable:
                    logger.debug(f"Transfers not available: {e}")
                    break
                raise

        return transfers

    async def fetch_refunds(self, transaction_id: str) -> list[dict]:
        """Fetch refunds for a transaction."""
        refunds = []
        page = 0
        size = 100

        while True:
            url = f"{self.base_url}/api/v1/refunds"
            params = {
                "pageNo": page,
                "pageSize": size,
                "transactionReference": transaction_id,
            }

            try:
                response = await self._request_with_retry(
                    "GET",
                    url,
                    headers=self.headers,
                    params=params,
                )

                if response.get("status") != "success":
                    logger.debug(f"No refunds found for transaction {transaction_id}")
                    break

                content = response.get("content", [])
                refunds.extend(content)

                # Check if there are more pages
                if not response.get("hasNext", False):
                    break

                page += 1

            except ProviderError as e:
                if not e.retryable:
                    logger.debug(f"Refunds not available: {e}")
                    break
                raise

        return refunds

    async def get_provider_health(self) -> dict:
        """Get provider health status."""
        import time

        try:
            start_time = time.time()
            url = f"{self.base_url}/api/v1/transactions/search"
            response = await self._request_with_retry(
                "GET",
                url,
                headers=self.headers,
                params={"pageNo": 0, "pageSize": 1},
            )
            latency_ms = int((time.time() - start_time) * 1000)

            if response.get("status") == "success":
                return {
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now().isoformat(),
                    "message": response.get("message"),
                }

        except ProviderTimeoutError:
            return {
                "status": "down",
                "latency_ms": None,
                "timestamp": datetime.now().isoformat(),
                "error": "Timeout",
            }
        except ProviderError as e:
            return {
                "status": "down" if not e.retryable else "degraded",
                "latency_ms": None,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }
