# DEPRECATED: Use src.bomipay.services.adapters instead
# This module is kept for backwards compatibility; new code should import from
# bomipay.services.adapters (e.g. ``from bomipay.services.adapters import get_adapter``).
"""Flutterwave provider adapter."""
import logging
from datetime import datetime
from typing import Any

from .provider_adapters_async import BaseAsyncProviderAdapter, ProviderError, ProviderTimeoutError

logger = logging.getLogger("bomipay")


class FlutterwaveAdapter(BaseAsyncProviderAdapter):
    """Flutterwave payment provider adapter."""

    provider_name = "flutterwave"
    base_url = "https://api.flutterwave.com/v3"

    def __init__(self, api_key: str, timeout: int = 30):
        super().__init__(api_key, timeout)
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def verify_transaction(self, reference: str) -> dict:
        """Verify transaction by reference."""
        url = f"{self.base_url}/transactions/{reference}/verify"
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
        page = 1
        size = 100

        while True:
            url = f"{self.base_url}/transactions"
            params = {
                "page": page,
                "size": size,
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
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

            data = response.get("data", [])
            transactions.extend(data)

            # Check if there are more pages
            meta = response.get("meta", {})
            if not meta.get("pagination", {}).get("has_more", False):
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
        page = 1
        size = 100

        while True:
            url = f"{self.base_url}/settlements"
            params = {
                "page": page,
                "size": size,
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
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

                data = response.get("data", [])
                settlements.extend(data)

                # Check if there are more pages
                meta = response.get("meta", {})
                if not meta.get("pagination", {}).get("has_more", False):
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
        page = 1
        size = 100

        while True:
            url = f"{self.base_url}/transfers"
            params = {
                "page": page,
                "size": size,
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
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

                data = response.get("data", [])

                # Filter by date range
                for item in data:
                    created_at = item.get("created_at")
                    if created_at:
                        try:
                            item_date = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                            if date_from <= item_date <= date_to:
                                transfers.append(item)
                        except (ValueError, AttributeError):
                            transfers.append(item)
                    else:
                        transfers.append(item)

                # Check if there are more pages
                meta = response.get("meta", {})
                if not meta.get("pagination", {}).get("has_more", False):
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
        page = 1
        size = 100

        while True:
            url = f"{self.base_url}/transactions/{transaction_id}/refunds"
            params = {
                "page": page,
                "size": size,
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

                data = response.get("data", [])
                refunds.extend(data)

                # Check if there are more pages
                meta = response.get("meta", {})
                if not meta.get("pagination", {}).get("has_more", False):
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
            url = f"{self.base_url}/transactions"
            response = await self._request_with_retry(
                "GET",
                url,
                headers=self.headers,
                params={"page": 1, "size": 1},
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
