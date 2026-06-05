import logging
import contextvars
from logging import LoggerAdapter
from typing import Any

from pythonjsonlogger import jsonlogger

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "secret_key",
        "api_key",
        "password",
        "token",
        "authorization",
        "secret",
        "private_key",
        "access_token",
        "refresh_token",
    }
)


class SensitiveDataFilter(logging.Filter):
    """Mask sensitive fields in log records before they are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in list(vars(record).keys()):
            if attr.lower() in _SENSITIVE_KEYS:
                setattr(record, attr, "***")
        return True

# Context variables propagated automatically through async call chains.
_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
_tenant_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tenant_id", default=""
)
_provider_name_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "provider_name", default=""
)

# Mapping used by LogContext to look up context vars by field name.
_CONTEXT_VARS: dict[str, contextvars.ContextVar[str]] = {
    "correlation_id": _correlation_id_var,
    "request_id": _request_id_var,
    "tenant_id": _tenant_id_var,
    "provider_name": _provider_name_var,
}


def set_log_context(
    *,
    correlation_id: str = "",
    request_id: str = "",
    tenant_id: str = "",
    provider_name: str = "",
) -> None:
    """Store structured fields in the current async context."""
    if correlation_id:
        _correlation_id_var.set(correlation_id)
    if request_id:
        _request_id_var.set(request_id)
    if tenant_id:
        _tenant_id_var.set(tenant_id)
    if provider_name:
        _provider_name_var.set(provider_name)


class LogContext:
    """
    Context manager that binds extra structured fields to all log calls made
    within its scope, without requiring explicit argument passing.

    Usage::

        with LogContext(tenant_id="acme", provider_name="paystack"):
            logger.info("processing webhook")  # fields injected automatically
    """

    def __init__(self, **fields: str) -> None:
        self._fields = fields
        self._tokens: list[tuple[contextvars.ContextVar[str], contextvars.Token[str]]] = []

    def __enter__(self) -> "LogContext":
        for key, value in self._fields.items():
            var = _CONTEXT_VARS.get(key)
            if var is not None and value:
                self._tokens.append((var, var.set(value)))
        return self

    def __exit__(self, *_: object) -> None:
        for var, token in self._tokens:
            var.reset(token)
        self._tokens.clear()


class _ContextAdapter(LoggerAdapter):
    """LoggerAdapter that automatically injects all structured context fields."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra: dict = kwargs.get("extra") or {}
        extra.setdefault("correlation_id", _correlation_id_var.get())
        extra.setdefault("request_id", _request_id_var.get())
        extra.setdefault("tenant_id", _tenant_id_var.get())
        extra.setdefault("provider_name", _provider_name_var.get())
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> _ContextAdapter:
    """Return a logger bound to the current request context."""
    return _ContextAdapter(logging.getLogger(name), {})


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers = []
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
