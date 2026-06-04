"""Provider response normalization."""
from datetime import datetime
from typing import Any, Optional


class ProviderNormalizer:
    """Normalize provider-specific responses to canonical format."""

    @staticmethod
    def normalize_transaction(provider_name: str, raw_txn: dict) -> dict:
        """
        Normalize transaction from provider to canonical format.

        Returns:
            {
                "provider_transaction_id": str,
                "amount": int (minor units),
                "currency": str,
                "status": "success"|"pending"|"failed",
                "customer_email": str,
                "timestamp": datetime,
                "metadata": {...}
            }
        """
        if provider_name == "paystack":
            return ProviderNormalizer._normalize_paystack_transaction(raw_txn)
        elif provider_name == "flutterwave":
            return ProviderNormalizer._normalize_flutterwave_transaction(raw_txn)
        elif provider_name == "monnify":
            return ProviderNormalizer._normalize_monnify_transaction(raw_txn)
        else:
            return ProviderNormalizer._normalize_generic_transaction(raw_txn)

    @staticmethod
    def _normalize_paystack_transaction(raw_txn: dict) -> dict:
        """Normalize Paystack transaction."""
        status_map = {
            "success": "success",
            "failed": "failed",
            "abandoned": "failed",
            "returned": "failed",
            "pending": "pending",
        }

        status = raw_txn.get("status", "pending")
        created_at = raw_txn.get("created_at") or raw_txn.get("transaction_date")

        return {
            "provider_transaction_id": str(raw_txn.get("id") or raw_txn.get("reference") or ""),
            "amount": int(raw_txn.get("amount", 0)),
            "currency": raw_txn.get("currency", "NGN").upper(),
            "status": status_map.get(status, "pending"),
            "customer_email": raw_txn.get("customer", {}).get("email") if isinstance(raw_txn.get("customer"), dict) else None,
            "timestamp": ProviderNormalizer._parse_iso_datetime(created_at),
            "metadata": raw_txn.get("metadata", {}),
        }

    @staticmethod
    def _normalize_flutterwave_transaction(raw_txn: dict) -> dict:
        """Normalize Flutterwave transaction."""
        status_map = {
            "successful": "success",
            "completed": "success",
            "failed": "failed",
            "pending": "pending",
        }

        status = raw_txn.get("status", "pending")
        created_at = raw_txn.get("created_at") or raw_txn.get("tx_date")

        return {
            "provider_transaction_id": str(raw_txn.get("id") or raw_txn.get("flw_ref") or ""),
            "amount": int(raw_txn.get("amount", 0)),
            "currency": raw_txn.get("currency", "NGN").upper(),
            "status": status_map.get(status, "pending"),
            "customer_email": raw_txn.get("customer", {}).get("email") if isinstance(raw_txn.get("customer"), dict) else None,
            "timestamp": ProviderNormalizer._parse_iso_datetime(created_at),
            "metadata": raw_txn.get("meta", {}),
        }

    @staticmethod
    def _normalize_monnify_transaction(raw_txn: dict) -> dict:
        """Normalize Monnify transaction."""
        status_map = {
            "PAID": "success",
            "COMPLETED": "success",
            "PENDING": "pending",
            "FAILED": "failed",
            "REVERSED": "failed",
        }

        status = raw_txn.get("paymentStatus", "PENDING")
        created_at = raw_txn.get("createdOn") or raw_txn.get("transactionDate")

        return {
            "provider_transaction_id": str(raw_txn.get("transactionReference") or raw_txn.get("id") or ""),
            "amount": int(raw_txn.get("transactionAmount", 0)),
            "currency": raw_txn.get("currency", "NGN").upper(),
            "status": status_map.get(status, "pending"),
            "customer_email": raw_txn.get("customerEmail") or (
                raw_txn.get("customer", {}).get("email") if isinstance(raw_txn.get("customer"), dict) else None
            ),
            "timestamp": ProviderNormalizer._parse_iso_datetime(created_at),
            "metadata": raw_txn.get("metadata", {}),
        }

    @staticmethod
    def _normalize_generic_transaction(raw_txn: dict) -> dict:
        """Normalize generic transaction."""
        return {
            "provider_transaction_id": str(raw_txn.get("id") or raw_txn.get("reference") or ""),
            "amount": int(raw_txn.get("amount", 0)),
            "currency": raw_txn.get("currency", "NGN").upper(),
            "status": raw_txn.get("status", "pending"),
            "customer_email": raw_txn.get("customer_email"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw_txn.get("created_at")),
            "metadata": raw_txn.get("metadata", {}),
        }

    @staticmethod
    def normalize_settlement(provider_name: str, raw_settlement: dict) -> dict:
        """Normalize settlement from provider."""
        if provider_name == "paystack":
            return ProviderNormalizer._normalize_paystack_settlement(raw_settlement)
        elif provider_name == "flutterwave":
            return ProviderNormalizer._normalize_flutterwave_settlement(raw_settlement)
        elif provider_name == "monnify":
            return ProviderNormalizer._normalize_monnify_settlement(raw_settlement)
        else:
            return ProviderNormalizer._normalize_generic_settlement(raw_settlement)

    @staticmethod
    def _normalize_paystack_settlement(raw: dict) -> dict:
        """Normalize Paystack settlement."""
        status_map = {
            "pending": "pending",
            "processing": "pending",
            "completed": "success",
            "failed": "failed",
        }

        return {
            "provider_settlement_id": str(raw.get("id") or raw.get("reference") or ""),
            "amount": int(raw.get("amount", 0)),
            "currency": raw.get("currency", "NGN").upper(),
            "status": status_map.get(raw.get("status", "pending"), "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw.get("created_at")),
            "metadata": raw.get("metadata", {}),
        }

    @staticmethod
    def _normalize_flutterwave_settlement(raw: dict) -> dict:
        """Normalize Flutterwave settlement."""
        status_map = {
            "pending": "pending",
            "processing": "pending",
            "completed": "success",
            "failed": "failed",
        }

        return {
            "provider_settlement_id": str(raw.get("id") or raw.get("reference") or ""),
            "amount": int(raw.get("amount", 0)),
            "currency": raw.get("currency", "NGN").upper(),
            "status": status_map.get(raw.get("status", "pending"), "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw.get("created_at")),
            "metadata": raw.get("meta", {}),
        }

    @staticmethod
    def _normalize_monnify_settlement(raw: dict) -> dict:
        """Normalize Monnify settlement."""
        status_map = {
            "PENDING": "pending",
            "PROCESSING": "pending",
            "COMPLETED": "success",
            "FAILED": "failed",
        }

        return {
            "provider_settlement_id": str(raw.get("id") or raw.get("reference") or ""),
            "amount": int(raw.get("amount", 0)),
            "currency": raw.get("currency", "NGN").upper(),
            "status": status_map.get(raw.get("status", "PENDING"), "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw.get("createdOn")),
            "metadata": raw.get("metadata", {}),
        }

    @staticmethod
    def _normalize_generic_settlement(raw: dict) -> dict:
        """Normalize generic settlement."""
        return {
            "provider_settlement_id": str(raw.get("id") or raw.get("reference") or ""),
            "amount": int(raw.get("amount", 0)),
            "currency": raw.get("currency", "NGN").upper(),
            "status": raw.get("status", "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw.get("created_at")),
            "metadata": raw.get("metadata", {}),
        }

    @staticmethod
    def normalize_transfer(provider_name: str, raw_transfer: dict) -> dict:
        """Normalize transfer from provider."""
        # Generic implementation - can be specialized per provider if needed
        return {
            "provider_transfer_id": str(raw_transfer.get("id") or raw_transfer.get("reference") or ""),
            "amount": int(raw_transfer.get("amount", 0)),
            "currency": raw_transfer.get("currency", "NGN").upper(),
            "status": raw_transfer.get("status", "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw_transfer.get("created_at")),
            "metadata": raw_transfer.get("metadata", {}),
        }

    @staticmethod
    def normalize_refund(provider_name: str, raw_refund: dict) -> dict:
        """Normalize refund from provider."""
        # Generic implementation - can be specialized per provider if needed
        return {
            "provider_refund_id": str(raw_refund.get("id") or raw_refund.get("reference") or ""),
            "amount": int(raw_refund.get("amount", 0)),
            "currency": raw_refund.get("currency", "NGN").upper(),
            "status": raw_refund.get("status", "pending"),
            "timestamp": ProviderNormalizer._parse_iso_datetime(raw_refund.get("created_at")),
            "metadata": raw_refund.get("metadata", {}),
        }

    @staticmethod
    def _parse_iso_datetime(value: Any) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object."""
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                # Try ISO format with timezone
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

            try:
                # Try common Paystack format
                return datetime.fromisoformat(value)
            except (ValueError, AttributeError):
                pass

        return None
