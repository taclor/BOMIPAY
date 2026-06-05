"""Provider adapter registry — single source of truth for adapter instantiation."""
from typing import Optional

from .base import ProviderAdapter
from .flutterwave import FlutterwaveAdapter
from .monnify import MonnifyAdapter
from .paystack import PaystackAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    "paystack": PaystackAdapter,
    "flutterwave": FlutterwaveAdapter,
    "monnify": MonnifyAdapter,
}


def get_adapter(
    provider_name: str,
    api_key: str,
    secret_key: Optional[str] = None,
) -> ProviderAdapter:
    """Instantiate and return the adapter for *provider_name*.

    Args:
        provider_name: Case-insensitive provider identifier (e.g. "paystack").
        api_key: Provider API key / public key.
        secret_key: Provider secret key (required for Monnify; optional otherwise).

    Raises:
        ValueError: If *provider_name* is not registered.
    """
    cls = ADAPTERS.get(provider_name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown provider: {provider_name!r}. "
            f"Available: {', '.join(ADAPTERS)}"
        )
    return cls(api_key=api_key, secret_key=secret_key)
