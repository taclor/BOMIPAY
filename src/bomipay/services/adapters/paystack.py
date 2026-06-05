"""Paystack provider adapter — consolidated from paystack_adapter.py + paystack_adapter_new.py."""
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
    ProviderAuthError,
    ProviderError,
    ProviderHealthStatus,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger("bomipay")

_STATUS_MAP = {
    "success": "success",
    "failed": "failed",
    "abandoned": "failed",
    "returned": "failed",
    "pending": "pending",
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
    fees = data.get("fees")
    fee_minor = int(fees) if fees is not None else None
    paid_at = data.get("paid_at") or data.get("transaction_date")
    return AdapterTransaction(
        provider_transaction_id=str(data.get("id") or data.get("reference") or ""),
        amount_minor=int(data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_STATUS_MAP.get(data.get("status", "pending"), "pending"),
        reference=str(data.get("reference") or ""),
        raw_payload=data,
        fee_minor=fee_minor,
        settled_at=_parse_dt(paid_at),
        metadata=data.get("metadata"),
    )


def _to_adapter_settlement(data: dict) -> AdapterSettlement:
    return AdapterSettlement(
        provider_settlement_id=str(data.get("id") or data.get("reference") or ""),
        amount_minor=int(data.get("amount", 0)),
        currency=data.get("currency", "NGN"),
        status=_SETTLEMENT_STATUS_MAP.get(data.get("status", "pending"), "pending"),
        settled_at=_parse_dt(data.get("settled_date") or data.get("created_at")),
        raw_payload=data,
    )


class PaystackAdapter(ProviderAdapter):
    """Paystack payment provider adapter."""

    provider_name = "paystack"
    base_url = "https://api.paystack.co"

    def __init__(self, api_key: str, secret_key: Optional[str] = None, timeout: int = 30):
        super().__init__(api_key=api_key, secret_key=secret_key, timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    # ------------------------------------------------------------------
    # Transaction methods
    # ------------------------------------------------------------------

    async def verify_transaction(self, reference: str) -> AdapterTransaction:
        url = f"{self.base_url}/transaction/verify/{reference}"
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
            params: dict = {"perPage": per_page, "page": current_page}
            if from_date:
                params["from"] = int(from_date.timestamp())
            if to_date:
                params["to"] = int(to_date.timestamp())

            response = await self._request_with_retry(
                "GET", f"{self.base_url}/transaction", headers=self._headers, params=params
            )
            if response.get("status") != "success":
                raise ProviderError(
                    f"Failed to fetch transactions: {response.get('message')}",
                    retryable=False,
                )

            data = response.get("data", [])
            transactions.extend(_to_adapter_txn(item) for item in data)

            meta = response.get("meta", {})
            if current_page >= meta.get("pageCount", 1):
                break
            current_page += 1

        return transactions

    # ------------------------------------------------------------------
    # Settlements
    # ------------------------------------------------------------------

    async def fetch_settlements(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[AdapterSettlement]:
        settlements: list[AdapterSettlement] = []
        page = 1
        per_page = 100

        while True:
            params: dict = {"perPage": per_page, "page": page}
            if from_date:
                params["from"] = int(from_date.timestamp())
            if to_date:
                params["to"] = int(to_date.timestamp())

            try:
                response = await self._request_with_retry(
                    "GET", f"{self.base_url}/settlement", headers=self._headers, params=params
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

            meta = response.get("meta", {})
            if page >= meta.get("pageCount", 1):
                break
            page += 1

        return settlements

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------

    async def fetch_transfers(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        transfers: list[dict] = []
        page = 1
        per_page = 100

        while True:
            try:
                response = await self._request_with_retry(
                    "GET",
                    f"{self.base_url}/transfer",
                    headers=self._headers,
                    params={"perPage": per_page, "page": page},
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
                created_at = item.get("createdAt")
                if created_at and from_date and to_date:
                    try:
                        item_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if not (from_date <= item_date <= to_date):
                            continue
                    except (ValueError, AttributeError):
                        pass
                transfers.append(item)

            meta = response.get("meta", {})
            if page >= meta.get("pageCount", 1):
                break
            page += 1

        return transfers

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    async def fetch_refunds(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[dict]:
        refunds: list[dict] = []
        page = 1
        per_page = 100

        while True:
            params: dict = {"perPage": per_page, "page": page}
            if from_date:
                params["from"] = int(from_date.timestamp())
            if to_date:
                params["to"] = int(to_date.timestamp())

            try:
                response = await self._request_with_retry(
                    "GET", f"{self.base_url}/refund", headers=self._headers, params=params
                )
            except ProviderError as exc:
                if not exc.retryable:
                    logger.debug("Refunds not available: %s", exc)
                    break
                raise

            if response.get("status") != "success":
                logger.debug("No refunds found: %s", response.get("message"))
                break

            refunds.extend(response.get("data", []))

            meta = response.get("meta", {})
            if page >= meta.get("pageCount", 1):
                break
            page += 1

        return refunds

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_provider_health(self) -> ProviderHealthStatus:
        start = time.monotonic()
        try:
            response = await self._request_with_retry(
                "GET",
                f"{self.base_url}/bank",
                headers=self._headers,
                params={"perPage": 1},
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

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    async def process_webhook(self, payload: dict, signature: str) -> dict:
        """Verify Paystack webhook HMAC-SHA512 and return normalized event dict.

        Note: Pass the raw request body as JSON-serialized bytes to *signature*
        for HMAC verification; ``payload`` is the already-parsed dict.
        """
        if self.secret_key:
            raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
            computed = hmac.new(
                self.secret_key.encode("utf-8"), raw_body, hashlib.sha512
            ).hexdigest()
            if not hmac.compare_digest(computed, signature or ""):
                raise ValueError("Invalid Paystack webhook signature")

        event = payload.get("event")
        data = payload.get("data", {})
        if not data:
            raise ValueError("Invalid Paystack webhook payload")

        status = data.get("status", "pending")
        if status == "success":
            normalized_status = "success"
        elif status in {"failed", "abandoned", "returned"}:
            normalized_status = "failed"
        else:
            normalized_status = "pending"

        customer = data.get("customer") or {}
        amount = data.get("amount", 0)
        fees = data.get("fees") or {}
        fee_amount = fees.get("amount", 0) if isinstance(fees, dict) else 0
        net_amount = amount - fee_amount

        metadata = data.get("metadata") or {}
        return {
            "provider_name": self.provider_name,
            "provider_event_id": str(
                data.get("id") or payload.get("id") or payload.get("reference") or event
            ),
            "event_type": event,
            "transaction_data": {
                "merchant_id": metadata.get("merchant_id"),
                "provider_name": self.provider_name,
                "provider_transaction_id": str(data.get("id") or data.get("reference") or ""),
                "external_reference": str(data.get("reference") or ""),
                "internal_reference": str(data.get("reference") or data.get("id") or ""),
                "payment_type": data.get("channel"),
                "payment_channel": data.get("channel"),
                "currency": data.get("currency", "NGN"),
                "amount": int(amount),
                "fee_amount": int(fee_amount),
                "net_amount": int(net_amount),
                "status": normalized_status,
                "status_reason": data.get("gateway_response") or data.get("failure_message"),
                "customer_name": " ".join(
                    filter(None, [customer.get("first_name"), customer.get("last_name")])
                ) or None,
                "customer_email": customer.get("email"),
                "customer_phone": customer.get("phone"),
                "metadata_json": data.get("metadata", {}),
            },
            "provider_payload": payload,
        }
