"""Sentry error reporting — optional, skipped silently when DSN not provided."""
import logging

logger = logging.getLogger("bomipay.sentry")


def setup_sentry(dsn: str | None) -> None:
    """
    Initialise Sentry SDK.

    Skips initialisation when *dsn* is ``None`` or empty.  If sentry-sdk is not
    installed the function returns silently.
    """
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry integration skipped")
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("sentry.initialized")


def set_sentry_context(
    *,
    correlation_id: str | None = None,
    merchant_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Attach request context to the active Sentry scope."""
    try:
        import sentry_sdk
    except ImportError:
        return

    with sentry_sdk.configure_scope() as scope:
        if correlation_id:
            scope.set_tag("correlation_id", correlation_id)
        if merchant_id:
            scope.set_tag("merchant_id", merchant_id)
            scope.set_user({"id": merchant_id})
        if tenant_id:
            scope.set_tag("tenant_id", tenant_id)
