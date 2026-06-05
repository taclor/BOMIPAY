"""Flutterwave provider adapter."""
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Optional

from .base import (
    AdapterSettlement,
    AdapterTransaction,
    ProviderAdapter,
    ProviderError,
    ProviderHealthStatus,
    ProviderTimeoutError,
)

logger = logging.getLogger("bomipay")

_STATUS_MAP = {
    "successful": "success",
    "completed": "success",
    "failed": "failed",
    "pending": "pending",
    "new": "pending",
}

_SETTLEMENT_STATUS_MAP = {
    "pending": "pending",
    "processing": "pending",
    "completed": "success",
    "failed": "failed",
}


def _parse_dt(value: object) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _to_adapter_txn(data: dict) -> AdapterTransaction:
    return AdapterTransaction(
        provider_transaction_id=str(data.get("id") or data.get("flw_ref") or ""),
        amount_minor=int(data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_STATUS_MAP.get(data.get("status", "pending"), "pending"),
        reference=str(data.get("tx_ref") or data.get("flw_ref") or ""),
        raw_payload=data,
        fee_minor=int(data.get("app_fee", 0)) if data.get("app_fee") is not None else None,
        settled_at=_parse_dt(data.get("created_at")),
        metadata=data.get("meta"),
    )


def _to_adapter_settlement(data: dict) -> AdapterSettlement:
    return AdapterSettlement(
        provider_settlement_id=str(data.get("id") or data.get("reference") or ""),
        amount_minor=int(data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_SETTLEMENT_STATUS_MAP.get(data.get("status", "pending"), "pending"),
        settled_at=_parse_dt(data.get("created_at")),
        raw_payload=data,
    )


class FlutterwaveAdapter(ProviderAdapter):
    """Flutterwave payment provider adapter."""

    provider_name = "flutterwave"
    base_url = "https://api.flutterwave.com/v3"

    def __init__(self, api_key: str, secret_key: Optional[str] = None, timeout: int = 30):
        super().__init__(api_key=api_key, secret_key=secret_key, timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def verify_transaction(self, reference: str) -> AdapterTransaction:
        url = f"{self.base_url}/transactions/{reference}/verify"
        response = await self._request_with_retry("GET", url, headers=self._headers)
        if response.get("status") != "success":
            raise ProviderError(
                f"Failed to verify transaction: {response.get('message')}",
                retryable=False,
            )
        return _to_adapter_txn(response.get("data", {}))

    async def fetch_transaction(self, provider_id: str) -> AdapterTransaction:
        return await self.verify_transaction(provider_id)

    async def fetch_transactions(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> list[AdapterTransaction]:
        transactions: list[AdapterTransaction] = []
        current_page = page

        while True:
            params: dict = {"page": current_page, "limit": per_page}
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()

            response = await self._request_with_retry(
                "GET", f"{self.base_url}/transactions", headers=self._headers, params=params
            )
            if response.get("status") != "success":
                raise ProviderError(
                    f"Failed to fetch transactions: {response.get('message')}",
                    retryable=False,
                )

            data = response.get("data", [])
            transactions.extend(_to_adapter_txn(item) for item in data)

            if not response.get("meta", {}).get("pagination", {}).get("has_more", False):
                break
            current_page += 1

        return transactions

    async def fetch_settlements(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[AdapterSettlement]:
        settlements: list[AdapterSettlement] = []
        page = 1
        per_page = 100

        while True:
            params: dict = {"page": page, "size": per_page}
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()

            try:
                response = await self._request_with_retry(
                    "GET", f"{self.base_url}/settlements", headers=self._headers, params=params
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Settlements not available: %s", exc)
                    break
                raise

            if response.get("status") != "success":
                logger.warning("Failed to fetch settlements: %s", response.get("message"))
                break

            data = response.get("data", [])
            settlements.extend(_to_adapter_settlement(item) for item in data)

            if not response.get("meta", {}).get("pagination", {}).get("has_more", False):
                break
            page += 1

        return settlements

    async def fetch_transfers(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        transfers: list[dict] = []
        page = 1
        per_page = 100

        while True:
            params: dict = {"page": page, "size": per_page}
            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()

            try:
                response = await self._request_with_retry(
                    "GET", f"{self.base_url}/transfers", headers=self._headers, params=params
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Transfers not available: %s", exc)
                    break
                raise

            if response.get("status") != "success":
                logger.warning("Failed to fetch transfers: %s", response.get("message"))
                break

            for item in response.get("data", []):
                created_at = item.get("created_at")
                if created_at and from_date and to_date:
                    try:
                        item_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if not (from_date <= item_date <= to_date):
                            continue
                    except (ValueError, AttributeError):
                        pass
                transfers.append(item)

            if not response.get("meta", {}).get("pagination", {}).get("has_more", False):
                break
            page += 1

        return transfers

    async def fetch_refunds(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        # Flutterwave refunds are per-transaction; date-range listing is not standard.
        # Return an empty list when called without a specific transaction context.
        logger.debug("Flutterwave refund listing by date range is not supported; returning []")
        return []

    async def get_provider_health(self) -> ProviderHealthStatus:
        start = time.monotonic()
        try:
            response = await self._request_with_retry(
                "GET",
                f"{self.base_url}/transactions",
                headers=self._headers,
                params={"page": 1, "limit": 1},
            )
            latency_ms = (time.monotonic() - start) * 1000
            is_healthy = response.get("status") == "success"
            return ProviderHealthStatus(
                is_healthy=is_healthy,
                latency_ms=latency_ms,
                success_rate=None,
                last_checked_at=datetime.utcnow(),
                error_message=None if is_healthy else response.get("message"),
            )
        except ProviderTimeoutError as exc:
            return ProviderHealthStatus(
                is_healthy=False,
                latency_ms=None,
                success_rate=None,
                last_checked_at=datetime.utcnow(),
                error_message=str(exc),
            )
        except ProviderError as exc:
            return ProviderHealthStatus(
                is_healthy=False,
                latency_ms=None,
                success_rate=None,
                last_checked_at=datetime.utcnow(),
                error_message=str(exc),
            )

    async def process_webhook(self, payload: dict, signature: str) -> dict:
        """Verify Flutterwave webhook (secret-hash header) and return normalized event."""
        if self.secret_key and signature != self.secret_key:
            raise ValueError("Invalid Flutterwave webhook secret-hash")

        data = payload.get("data", {})
        event = payload.get("event", "")

        status_raw = data.get("status", "pending")
        normalized_status = _STATUS_MAP.get(status_raw, "pending")

        customer = data.get("customer") or {}
        return {
            "provider_name": self.provider_name,
            "provider_event_id": str(data.get("id") or data.get("flw_ref") or event),
            "event_type": event,
            "transaction_data": {
                "provider_name": self.provider_name,
                "provider_transaction_id": str(data.get("id") or data.get("flw_ref") or ""),
                "external_reference": str(data.get("tx_ref") or ""),
                "currency": data.get("currency", "NGN"),
                "amount": int(data.get("amount", 0)),
                "fee_amount": int(data.get("app_fee", 0)),
                "status": normalized_status,
                "customer_email": customer.get("email"),
                "customer_name": customer.get("name"),
                "customer_phone": customer.get("phone_number"),
                "metadata_json": data.get("meta", {}),
            },
            "provider_payload": payload,
        }
