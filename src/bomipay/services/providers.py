import abc
from typing import Any


class ProviderAdapter(abc.ABC):
    provider_name: str

    @abc.abstractmethod
    def verify_signature(self, headers: dict[str, str], body: bytes, secret: str) -> bool:
        pass

    @abc.abstractmethod
    def normalize_webhook(self, body: bytes) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def connect_account(self, credentials: dict[str, str]) -> bool:
        pass

    @abc.abstractmethod
    def get_provider_health(self, credentials: dict[str, str]) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def fetch_transaction(self, transaction_id: str) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def verify_transaction(self, transaction_id: str) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def fetch_transactions(self, merchant_id: str, date_from: str | None = None, date_to: str | None = None) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def fetch_settlements(self, merchant_id: str) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def fetch_transfers(self, merchant_id: str) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def fetch_refunds(self, merchant_id: str) -> list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    def process_webhook(self, headers: dict[str, str], body: bytes, secret: str) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def map_status(self, provider_status: str) -> str:
        pass

    @abc.abstractmethod
    def map_error_code(self, provider_code: str | None) -> str | None:
        pass


class ProviderAdapterRegistry:
    _adapters: dict[str, ProviderAdapter] = {}

    @classmethod
    def register(cls, adapter: ProviderAdapter) -> None:
        cls._adapters[adapter.provider_name] = adapter

    @classmethod
    def get_adapter(cls, provider_name: str) -> ProviderAdapter | None:
        return cls._adapters.get(provider_name)
