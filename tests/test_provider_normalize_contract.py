"""Contract tests for ProviderNormalizer.

Verifies that normalize_transaction() always produces the canonical output shape:
- provider_transaction_id: str
- amount: int  (minor or major units depending on provider, but always int)
- currency: str (uppercase)
- status: "success" | "pending" | "failed"
- customer_email: str | None
- timestamp: datetime | None
- metadata: dict
"""

from datetime import datetime

import pytest

from bomipay.services.provider_normalize import ProviderNormalizer

from fixtures.flutterwave_responses import FLW_VERIFY_SUCCESS
from fixtures.monnify_responses import (
    MONNIFY_VERIFY_COMPLETED,
    MONNIFY_VERIFY_FAILED,
    MONNIFY_VERIFY_PENDING,
    MONNIFY_VERIFY_SUCCESS,
)
from fixtures.paystack_responses import (
    PAYSTACK_VERIFY_ABANDONED,
    PAYSTACK_VERIFY_FAILED,
    PAYSTACK_VERIFY_PENDING,
    PAYSTACK_VERIFY_SUCCESS,
)

CANONICAL_FIELDS = {
    "provider_transaction_id",
    "amount",
    "currency",
    "status",
    "customer_email",
    "timestamp",
    "metadata",
}


@pytest.mark.staging
class TestProviderNormalizerContract:
    """normalize_transaction output must match the canonical schema."""

    def test_paystack_normalize_preserves_amount_as_integer(self):
        """Paystack amount (kobo) must be preserved as int."""
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["amount"] == 500000
        assert isinstance(result["amount"], int)

    def test_paystack_normalize_no_float_amounts(self):
        """No monetary field may be a float."""
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert isinstance(result["amount"], int), "amount must be int, not float"

    def test_paystack_normalize_maps_success_status(self):
        raw = {**PAYSTACK_VERIFY_SUCCESS["data"], "status": "success"}
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["status"] == "success"

    def test_paystack_normalize_maps_failed_status(self):
        raw = PAYSTACK_VERIFY_FAILED["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["status"] == "failed"

    def test_paystack_normalize_maps_abandoned_to_failed(self):
        """Paystack 'abandoned' maps to canonical 'failed'."""
        raw = PAYSTACK_VERIFY_ABANDONED["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["status"] == "failed"

    def test_paystack_normalize_maps_pending_status(self):
        raw = PAYSTACK_VERIFY_PENDING["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["status"] == "pending"

    def test_paystack_normalize_all_canonical_fields_present(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        missing = CANONICAL_FIELDS - set(result.keys())
        assert not missing, f"Missing canonical fields: {missing}"

    def test_paystack_normalize_currency_is_uppercase(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["currency"] == result["currency"].upper()
        assert result["currency"] == "NGN"

    def test_paystack_normalize_customer_email(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["customer_email"] == "user@example.com"

    def test_paystack_normalize_provider_transaction_id_is_string(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert isinstance(result["provider_transaction_id"], str)
        assert result["provider_transaction_id"] == "1234567"

    def test_paystack_normalize_timestamp_is_datetime_or_none(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert result["timestamp"] is None or isinstance(result["timestamp"], datetime)

    def test_paystack_normalize_metadata_is_dict(self):
        raw = PAYSTACK_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("paystack", raw)
        assert isinstance(result["metadata"], dict)

    # --- Flutterwave ---

    def test_flutterwave_normalize_amount_is_integer(self):
        raw = FLW_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("flutterwave", raw)
        assert isinstance(result["amount"], int)
        assert result["amount"] == 5000

    def test_flutterwave_normalize_maps_successful_to_success(self):
        """Flutterwave 'successful' maps to canonical 'success'."""
        raw = FLW_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("flutterwave", raw)
        assert result["status"] == "success"

    def test_flutterwave_normalize_all_canonical_fields_present(self):
        raw = FLW_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("flutterwave", raw)
        missing = CANONICAL_FIELDS - set(result.keys())
        assert not missing, f"Missing canonical fields: {missing}"

    def test_flutterwave_normalize_no_float_amounts(self):
        raw = FLW_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("flutterwave", raw)
        assert isinstance(result["amount"], int)

    # --- Monnify ---

    def test_monnify_normalize_amount_is_integer(self):
        raw = MONNIFY_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert isinstance(result["amount"], int)
        assert result["amount"] == 5000

    def test_monnify_normalize_maps_PAID_to_success(self):
        """Monnify 'PAID' maps to canonical 'success'."""
        raw = MONNIFY_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert result["status"] == "success"

    def test_monnify_normalize_maps_COMPLETED_to_success(self):
        raw = MONNIFY_VERIFY_COMPLETED["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert result["status"] == "success"

    def test_monnify_normalize_maps_PENDING_to_pending(self):
        raw = MONNIFY_VERIFY_PENDING["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert result["status"] == "pending"

    def test_monnify_normalize_maps_FAILED_to_failed(self):
        raw = MONNIFY_VERIFY_FAILED["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert result["status"] == "failed"

    def test_monnify_normalize_all_canonical_fields_present(self):
        raw = MONNIFY_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        missing = CANONICAL_FIELDS - set(result.keys())
        assert not missing, f"Missing canonical fields: {missing}"

    def test_monnify_normalize_no_float_amounts(self):
        raw = MONNIFY_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert isinstance(result["amount"], int)

    def test_monnify_normalize_customer_email(self):
        raw = MONNIFY_VERIFY_SUCCESS["data"]
        result = ProviderNormalizer.normalize_transaction("monnify", raw)
        assert result["customer_email"] == "user@example.com"

    # --- Settlement normalization ---

    def test_paystack_normalize_settlement_canonical_fields(self):
        raw_settlement = {
            "id": 999,
            "amount": 450000,
            "currency": "NGN",
            "status": "completed",
            "created_at": "2024-01-20T10:00:00.000Z",
            "metadata": {},
        }
        result = ProviderNormalizer.normalize_settlement("paystack", raw_settlement)
        assert isinstance(result["amount"], int)
        assert result["amount"] == 450000
        assert result["status"] == "success"
        assert "provider_settlement_id" in result
