"""Monnify provider adapter."""
import base64
import hashlib
import hmac
import json
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
    "PAID": "success",
    "COMPLETED": "success",
    "OVERPAYMENT": "success",
    "PENDING": "pending",
    "PENDING_PAYMENT": "pending",
    "FAILED": "failed",
    "REVERSED": "failed",
    "CANCELLED": "failed",
    "EXPIRED": "failed",
}

_SETTLEMENT_STATUS_MAP = {
    "PENDING": "pending",
    "PROCESSING": "pending",
    "COMPLETED": "success",
    "FAILED": "failed",
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
        provider_transaction_id=str(
            data.get("transactionReference") or data.get("paymentReference") or data.get("id") or ""
        ),
        amount_minor=int(data.get("transactionAmount") or data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_STATUS_MAP.get(data.get("paymentStatus", "PENDING"), "pending"),
        reference=str(data.get("paymentReference") or data.get("transactionReference") or ""),
        raw_payload=data,
        fee_minor=None,
        settled_at=_parse_dt(data.get("completedOn") or data.get("createdOn")),
        metadata=data.get("metadata"),
    )


def _to_adapter_settlement(data: dict) -> AdapterSettlement:
    return AdapterSettlement(
        provider_settlement_id=str(data.get("id") or data.get("reference") or ""),
        amount_minor=int(data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_SETTLEMENT_STATUS_MAP.get(data.get("status", "PENDING"), "pending"),
        settled_at=_parse_dt(data.get("createdOn") or data.get("settledOn")),
        raw_payload=data,
    )


class MonnifyAdapter(ProviderAdapter):
    """Monnify payment provider adapter.

    Monnify uses HTTP Basic Auth: base64(api_key:secret_key).
    """

    provider_name = "monnify"
    base_url = "https://api.monnify.com"

    def __init__(self, api_key: str, secret_key: Optional[str] = None, timeout: int = 30):
        super().__init__(api_key=api_key, secret_key=secret_key or "", timeout=timeout)
        credentials = f"{api_key}:{secret_key or ''}".encode()
        encoded = base64.b64encode(credentials).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def verify_transaction(self, reference: str) -> AdapterTransaction:
        url = f"{self.base_url}/api/v1/merchant/transactions/query"
        response = await self._request_with_retry(
            "GET", url, headers=self._headers, params={"paymentReference": reference}
        )
        if response.get("requestSuccessful") is not True:
            raise ProviderError(
                f"Failed to verify transaction: {response.get('responseMessage')}",
                retryable=False,
            )
        return _to_adapter_txn(response.get("responseBody", {}))

    async def fetch_transaction(self, provider_id: str) -> AdapterTransaction:
        return await self.verify_transaction(provider_id)

    async def fetch_transactions(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 0,
        per_page: int = 100,
    ) -> list[AdapterTransaction]:
        transactions: list[AdapterTransaction] = []
        current_page = page

        while True:
            params: dict = {"pageNo": current_page, "pageSize": per_page}
            if from_date:
                params["startDate"] = from_date.isoformat()
            if to_date:
                params["endDate"] = to_date.isoformat()

            response = await self._request_with_retry(
                "GET",
                f"{self.base_url}/api/v1/transactions/search",
                headers=self._headers,
                params=params,
            )
            if response.get("requestSuccessful") is not True and response.get("status") != "success":
                raise ProviderError(
                    f"Failed to fetch transactions: {response.get('responseMessage') or response.get('message')}",
                    retryable=False,
                )

            content = response.get("responseBody", {}).get("content", []) or response.get("content", [])
            transactions.extend(_to_adapter_txn(item) for item in content)

            body = response.get("responseBody", response)
            if not body.get("hasNext", False):
                break
            current_page += 1

        return transactions

    async def fetch_settlements(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[AdapterSettlement]:
        settlements: list[AdapterSettlement] = []
        page = 0
        per_page = 100

        while True:
            params: dict = {"pageNo": page, "pageSize": per_page}
            if from_date:
                params["startDate"] = from_date.isoformat()
            if to_date:
                params["endDate"] = to_date.isoformat()

            try:
                response = await self._request_with_retry(
                    "GET",
                    f"{self.base_url}/api/v1/settlements",
                    headers=self._headers,
                    params=params,
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Settlements not available: %s", exc)
                    break
                raise

            if response.get("requestSuccessful") is not True and response.get("status") != "success":
                logger.warning("Failed to fetch settlements: %s", response.get("responseMessage"))
                break

            body = response.get("responseBody", response)
            content = body.get("content", [])
            settlements.extend(_to_adapter_settlement(item) for item in content)

            if not body.get("hasNext", False):
                break
            page += 1

        return settlements

    async def fetch_transfers(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        transfers: list[dict] = []
        page = 0
        per_page = 100

        while True:
            params: dict = {"pageNo": page, "pageSize": per_page}
            if from_date:
                params["startDate"] = from_date.isoformat()
            if to_date:
                params["endDate"] = to_date.isoformat()

            try:
                response = await self._request_with_retry(
                    "GET",
                    f"{self.base_url}/api/v1/disbursements/search",
                    headers=self._headers,
                    params=params,
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Transfers not available: %s", exc)
                    break
                raise

            if response.get("requestSuccessful") is not True and response.get("status") != "success":
                logger.warning("Failed to fetch transfers: %s", response.get("responseMessage"))
                break

            body = response.get("responseBody", response)
            content = body.get("content", [])

            for item in content:
                created_on = item.get("createdOn")
                if created_on and from_date and to_date:
                    try:
                        item_date = datetime.fromisoformat(created_on.replace("Z", "+00:00"))
                        if not (from_date <= item_date <= to_date):
                            continue
                    except (ValueError, AttributeError):
                        pass
                transfers.append(item)

            if not body.get("hasNext", False):
                break
            page += 1

        return transfers

    async def fetch_refunds(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        refunds: list[dict] = []
        page = 0
        per_page = 100

        while True:
            params: dict = {"pageNo": page, "pageSize": per_page}

            try:
                response = await self._request_with_retry(
                    "GET",
                    f"{self.base_url}/api/v1/refunds",
                    headers=self._headers,
                    params=params,
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Refunds not available: %s", exc)
                    break
                raise

            if response.get("requestSuccessful") is not True and response.get("status") != "success":
                logger.debug("No refunds found: %s", response.get("responseMessage"))
                break

            body = response.get("responseBody", response)
            content = body.get("content", [])
            refunds.extend(content)

            if not body.get("hasNext", False):
                break
            page += 1

        return refunds

    async def get_provider_health(self) -> ProviderHealthStatus:
        start = time.monotonic()
        try:
            response = await self._request_with_retry(
                "GET",
                f"{self.base_url}/api/v1/transactions/search",
                headers=self._headers,
                params={"pageNo": 0, "pageSize": 1},
            )
            latency_ms = (time.monotonic() - start) * 1000
            is_healthy = (
                response.get("requestSuccessful") is True
                or response.get("status") == "success"
            )
            return ProviderHealthStatus(
                is_healthy=is_healthy,
                latency_ms=latency_ms,
                success_rate=None,
                last_checked_at=datetime.utcnow(),
                error_message=None if is_healthy else response.get("responseMessage"),
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
        """Verify Monnify HMAC-SHA512 webhook and return normalized event dict."""
        if self.secret_key:
            raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
            computed = hmac.new(
                self.secret_key.encode("utf-8"), raw_body, hashlib.sha512
            ).hexdigest()
            if not hmac.compare_digest(computed, signature or ""):
                raise ValueError("Invalid Monnify webhook signature")

        event_type = payload.get("eventType", "")
        event_data = payload.get("eventData", {})

        product = event_data.get("product", {})
        status_raw = event_data.get("paymentStatus", "PENDING")
        normalized_status = _STATUS_MAP.get(status_raw, "pending")

        return {
            "provider_name": self.provider_name,
            "provider_event_id": str(
                event_data.get("transactionReference")
                or event_data.get("paymentReference")
                or event_type
            ),
            "event_type": event_type,
            "transaction_data": {
                "provider_name": self.provider_name,
                "provider_transaction_id": str(
                    event_data.get("transactionReference") or ""
                ),
                "external_reference": str(event_data.get("paymentReference") or ""),
                "currency": event_data.get("currency", "NGN"),
                "amount": int(event_data.get("amountPaid") or event_data.get("totalPayable", 0)),
                "fee_amount": 0,
                "status": normalized_status,
                "customer_email": event_data.get("customer", {}).get("email"),
                "customer_name": event_data.get("customer", {}).get("name"),
                "metadata_json": event_data.get("metaData", {}),
            },
            "provider_payload": payload,
        }
