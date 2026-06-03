"""Domain exceptions for Bomi Pay.

Every exception maps to a specific HTTP status code via the error handler
middleware registered in main.py.
"""
from __future__ import annotations


class BomiPayError(Exception):
    """Base class for all Bomi Pay domain errors."""

    def __init__(self, message: str = "") -> None:
        self.message = message or self.__class__.__name__
        super().__init__(self.message)


class NotFoundError(BomiPayError):
    def __init__(self, resource: str, resource_id: str, message: str = "") -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(message or f"{resource} '{resource_id}' not found")


class PermissionDeniedError(BomiPayError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message)


class TenantIsolationError(BomiPayError):
    def __init__(self, message: str = "Tenant isolation violation") -> None:
        super().__init__(message)


class ValidationError(BomiPayError):
    def __init__(self, field: str, reason: str, message: str = "") -> None:
        self.field = field
        self.reason = reason
        super().__init__(message or f"Validation error on '{field}': {reason}")


class ConflictError(BomiPayError):
    def __init__(self, resource: str, message: str = "") -> None:
        self.resource = resource
        super().__init__(message or f"Conflict on {resource}")


class ProviderError(BomiPayError):
    def __init__(
        self,
        provider_name: str,
        retryable: bool = False,
        status_code: int | None = None,
        message: str = "",
    ) -> None:
        self.provider_name = provider_name
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message or f"Provider error from {provider_name}")


class ProviderTimeoutError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        status_code: int | None = None,
        message: str = "",
    ) -> None:
        super().__init__(
            provider_name,
            retryable=True,
            status_code=status_code,
            message=message or f"Provider {provider_name} timed out",
        )


class ProviderRateLimitError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        status_code: int | None = None,
        message: str = "",
    ) -> None:
        super().__init__(
            provider_name,
            retryable=True,
            status_code=status_code,
            message=message or f"Provider {provider_name} rate limited",
        )


class WebhookValidationError(BomiPayError):
    def __init__(self, provider_name: str, message: str = "") -> None:
        self.provider_name = provider_name
        super().__init__(message or f"Webhook validation failed for {provider_name}")


class DatabaseError(BomiPayError):
    def __init__(self, message: str = "Database error") -> None:
        super().__init__(message)


class IdempotencyConflictError(BomiPayError):
    def __init__(self, idempotency_key: str, message: str = "") -> None:
        self.idempotency_key = idempotency_key
        super().__init__(message or f"Idempotency conflict for key '{idempotency_key}'")
