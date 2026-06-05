# DEPRECATED: Use src.bomipay.services.adapters instead
# This module is kept for backwards compatibility; new code should import from
# bomipay.services.adapters (e.g. ``from bomipay.services.adapters import get_adapter``).
import hmac
import hashlib
import json
from datetime import datetime
from typing import Any

from .providers import ProviderAdapter, ProviderAdapterRegistry


class PaystackAdapter(ProviderAdapter):
    provider_name = "paystack"

    def verify_signature(self, headers: dict[str, str], body: bytes, secret: str) -> bool:
        signature = headers.get("x-paystack-signature")
        if not signature or not secret:
            return False
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, signature)

    def process_webhook(self, headers: dict[str, str], body: bytes, secret: str) -> dict[str, Any]:
        if not self.verify_signature(headers, body, secret):
            raise ValueError("Invalid Paystack webhook signature")
        return self.normalize_webhook(body)

    def normalize_webhook(self, body: bytes) -> dict[str, Any]:
        payload = json.loads(body)
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

        customer = data.get("customer", {}) or {}
        amount = data.get("amount", 0)
        fee_amount = data.get("fees", {}).get("amount", 0)
        net_amount = amount - fee_amount if amount is not None else None

        transaction_date = data.get("transaction_date")
        initiated_at = None
        if transaction_date:
            try:
                initiated_at = datetime.fromisoformat(transaction_date)
            except ValueError:
                initiated_at = None

        metadata = data.get("metadata", {}) or {}
        return {
            "provider_name": self.provider_name,
            "provider_event_id": str(data.get("id") or payload.get("id") or payload.get("reference") or event),
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
                "net_amount": int(net_amount) if net_amount is not None else None,
                "status": normalized_status,
                "status_reason": data.get("gateway_response") or data.get("failure_message"),
                "initiated_at": initiated_at,
                "confirmed_at": initiated_at if normalized_status == "success" else None,
                "settled_at": initiated_at if normalized_status == "success" else None,
                "customer_name": " ".join(filter(None, [customer.get("first_name"), customer.get("last_name")])) or None,
                "customer_email": customer.get("email"),
                "customer_phone": customer.get("phone"),
                "metadata_json": data.get("metadata", {}),
            },
            "provider_payload": payload,
        }

    # The following methods are stubs reserved for later sprints (provider sync,
    # health, verification, settlements). They are intentionally not implemented
    # yet but must be concrete so the adapter can be instantiated and registered.
    def connect_account(self, credentials: dict[str, str]) -> bool:  # pragma: no cover - stub
        # Basic validation of Paystack credentials
        return bool(credentials.get("api_key") and credentials.get("secret_key"))

    def get_provider_health(self, credentials: dict[str, str]) -> dict[str, Any]:  # pragma: no cover - stub
        # Return basic health status
        return {"status": "operational", "connected": True}

    def fetch_transaction(self, transaction_id: str) -> dict[str, Any]:  # pragma: no cover - stub
        # Stub implementation - returns empty dict for now
        return {}

    def verify_transaction(self, transaction_id: str) -> dict[str, Any]:  # pragma: no cover - stub
        raise NotImplementedError("Paystack verify_transaction is implemented in a later sprint")

    def fetch_transactions(self, merchant_id: str, date_from: str | None = None, date_to: str | None = None) -> list[dict[str, Any]]:  # pragma: no cover - stub
        return []

    def fetch_settlements(self, merchant_id: str) -> list[dict[str, Any]]:  # pragma: no cover - stub
        return []

    def fetch_transfers(self, merchant_id: str) -> list[dict[str, Any]]:  # pragma: no cover - stub
        return []

    def fetch_refunds(self, merchant_id: str) -> list[dict[str, Any]]:  # pragma: no cover - stub
        return []

    def map_status(self, provider_status: str) -> str:  # pragma: no cover - stub
        mapping = {
            "success": "success",
            "failed": "failed",
            "abandoned": "failed",
            "returned": "failed",
        }
        return mapping.get(provider_status, "pending")

    def map_error_code(self, provider_code: str | None) -> str | None:  # pragma: no cover - stub
        return provider_code


ProviderAdapterRegistry.register(PaystackAdapter())
