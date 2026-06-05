"""Provider adapter framework — public surface.

Usage::

    from bomipay.services.adapters import get_adapter, AdapterTransaction

    adapter = get_adapter("paystack", api_key="sk_live_...")
    txn = await adapter.verify_transaction("ref_abc123")
"""
from .base import (
    AdapterSettlement,
    AdapterTransaction,
    ProviderAdapter,
    ProviderHealthStatus,
)
from .registry import ADAPTERS, get_adapter

__all__ = [
    "AdapterTransaction",
    "AdapterSettlement",
    "ProviderAdapter",
    "ProviderHealthStatus",
    "ADAPTERS",
    "get_adapter",
]
