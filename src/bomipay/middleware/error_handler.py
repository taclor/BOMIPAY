"""Centralised exception → HTTP response mapping middleware."""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..exceptions import (
    BomiPayError,
    ConflictError,
    DatabaseError,
    IdempotencyConflictError,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    TenantIsolationError,
    ValidationError,
    WebhookValidationError,
)

logger = logging.getLogger("bomipay.errors")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ids(request: Request) -> tuple[str, str]:
    """Return (request_id, correlation_id) from request.state, generating if absent."""
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid4())
    return request_id, correlation_id


def _error_response(
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    request_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
                "request_id": request_id,
            }
        },
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Per-exception handlers
# ---------------------------------------------------------------------------

async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.warning(
        "error.not_found",
        extra={
            "resource": exc.resource,
            "resource_id": exc.resource_id,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(404, "NOT_FOUND", str(exc), correlation_id, request_id)


async def permission_denied_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.warning(
        "error.permission_denied",
        extra={"correlation_id": correlation_id, "request_id": request_id, "path": request.url.path},
    )
    return _error_response(403, "PERMISSION_DENIED", str(exc), correlation_id, request_id)


async def tenant_isolation_handler(request: Request, exc: TenantIsolationError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.warning(
        "error.tenant_isolation",
        extra={"correlation_id": correlation_id, "request_id": request_id, "path": request.url.path},
    )
    return _error_response(403, "TENANT_ISOLATION", str(exc), correlation_id, request_id)


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.info(
        "error.validation",
        extra={
            "field": exc.field,
            "reason": exc.reason,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(422, "VALIDATION_ERROR", str(exc), correlation_id, request_id)


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.info(
        "error.conflict",
        extra={
            "resource": exc.resource,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(409, "CONFLICT", str(exc), correlation_id, request_id)


async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.info(
        "error.idempotency_conflict",
        extra={
            "idempotency_key": exc.idempotency_key,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(409, "IDEMPOTENCY_CONFLICT", str(exc), correlation_id, request_id)


async def provider_timeout_handler(request: Request, exc: ProviderTimeoutError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.error(
        "error.provider_timeout",
        extra={
            "provider_name": exc.provider_name,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(504, "PROVIDER_TIMEOUT", str(exc), correlation_id, request_id)


async def provider_rate_limit_handler(request: Request, exc: ProviderRateLimitError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.warning(
        "error.provider_rate_limit",
        extra={
            "provider_name": exc.provider_name,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(429, "PROVIDER_RATE_LIMITED", str(exc), correlation_id, request_id)


async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    status_code = 502 if exc.retryable else 400
    logger.error(
        "error.provider",
        extra={
            "provider_name": exc.provider_name,
            "retryable": exc.retryable,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(status_code, "PROVIDER_ERROR", str(exc), correlation_id, request_id)


async def webhook_validation_handler(request: Request, exc: WebhookValidationError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.warning(
        "error.webhook_validation",
        extra={
            "provider_name": exc.provider_name,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(400, "WEBHOOK_VALIDATION_ERROR", str(exc), correlation_id, request_id)


async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.error(
        "error.database",
        extra={"correlation_id": correlation_id, "request_id": request_id, "path": request.url.path},
    )
    return _error_response(503, "DATABASE_ERROR", str(exc), correlation_id, request_id)


async def generic_bomipay_handler(request: Request, exc: BomiPayError) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    logger.error(
        "error.bomipay_unclassified",
        extra={
            "error_type": type(exc).__name__,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
    )
    return _error_response(500, "INTERNAL_ERROR", str(exc), correlation_id, request_id)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id, correlation_id = _get_ids(request)
    log_exc_info = settings.environment not in ("production", "staging")
    logger.error(
        "error.unhandled",
        extra={
            "error_type": type(exc).__name__,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "path": request.url.path,
        },
        exc_info=log_exc_info,
    )
    return _error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred. Please try again later.",
        correlation_id,
        request_id,
    )


# ---------------------------------------------------------------------------
# Registration helper called from main.py
# ---------------------------------------------------------------------------

def register_exception_handlers(app) -> None:
    """Register all BomiPay exception handlers with the FastAPI application.

    More specific subclasses are registered first so Starlette's MRO-based
    lookup resolves them before their parent classes.
    """
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    app.add_exception_handler(TenantIsolationError, tenant_isolation_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(IdempotencyConflictError, idempotency_conflict_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    # Subclasses of ProviderError first
    app.add_exception_handler(ProviderTimeoutError, provider_timeout_handler)
    app.add_exception_handler(ProviderRateLimitError, provider_rate_limit_handler)
    app.add_exception_handler(ProviderError, provider_error_handler)
    app.add_exception_handler(WebhookValidationError, webhook_validation_handler)
    app.add_exception_handler(DatabaseError, database_error_handler)
    # Catch-all for any remaining BomiPayError subclasses
    app.add_exception_handler(BomiPayError, generic_bomipay_handler)
    # NOTE: bare Exception is intentionally NOT registered here.
    # Starlette routes `add_exception_handler(Exception, ...)` to ServerErrorMiddleware,
    # which calls the handler but then re-raises — breaking ASGI transports in tests and
    # causing double-response in production.  Instead, unhandled_exception_handler is
    # called directly inside the http middleware's try/except in main.py.
