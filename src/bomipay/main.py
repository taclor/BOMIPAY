import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging import configure_logging, set_log_context
from .middleware.error_handler import register_exception_handlers, unhandled_exception_handler
from .middleware.rate_limit import setup_rate_limiting
from .middleware.security import setup_security_headers
from .observability.metrics import get_metrics_output
from .observability.sentry import setup_sentry
from .routes.auth import router as auth_router
from .routes.alerts import router as alerts_router
from .routes.health import router as health_router
from .routes.merchant import router as merchant_router
from .routes.transactions import router as transactions_router
from .routes.webhooks import router as webhooks_router
from .routes.providers import router as providers_router
from .routes.reconciliation import router as reconciliation_router
from .routes.notifications import router as notifications_router
from .routes.bank_accounts import router as bank_accounts_router
from .routes.data_sources import router as data_sources_router
from .routes.bank_statements import router as bank_statements_router
from .routes.provider_sync import router as provider_sync_router
from .routes.incidents import router as incidents_router
from .routes.analytics import router as analytics_router
from .routes.dashboard import router as dashboard_router
from .routes.timeline import router as timeline_router
from .routes.action_center import router as action_center_router
from .routes.payment_graph import router as payment_graph_router
from .routes.ai_assistant import router as ai_assistant_router

configure_logging()
logger = logging.getLogger("bomipay")

# Sentry initialised at import time so it captures startup errors too.
setup_sentry(settings.sentry_dsn)

# Tracing is set up once at module import.  Called here (not inside lifespan)
# so it is also idempotent across test collection.
from .observability.tracing import setup_tracing as _setup_tracing  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_tracing(app)
    logger.info("service.startup", extra={"environment": settings.environment})
    yield
    logger.info("service.shutdown")


_docs_kwargs = (
    {}
    if settings.docs_enabled
    else {"openapi_url": None, "docs_url": None, "redoc_url": None}
)

app = FastAPI(
    title="Bomi Pay API",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    **_docs_kwargs,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Paystack-Signature",
    ],
)

setup_security_headers(app)
setup_rate_limiting(app)
register_exception_handlers(app)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(merchant_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(providers_router, prefix="/api/v1")
app.include_router(reconciliation_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(bank_accounts_router, prefix="/api/v1")
app.include_router(data_sources_router, prefix="/api/v1")
app.include_router(bank_statements_router, prefix="/api/v1")
app.include_router(provider_sync_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(timeline_router, prefix="/api/v1")
app.include_router(action_center_router, prefix="/api/v1")
app.include_router(payment_graph_router, prefix="/api/v1")
app.include_router(ai_assistant_router, prefix="/api/v1")
app.include_router(webhooks_router)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    body, content_type = get_metrics_output()
    return Response(content=body, media_type=content_type)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())

    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    set_log_context(correlation_id=correlation_id, request_id=request_id)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        response = await unhandled_exception_handler(request, exc)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Correlation-ID", correlation_id)
        _record_http_metrics(request, response.status_code, time.perf_counter() - start)
        logger.info(
            "request.received",
            extra={
                "path": request.url.path,
                "method": request.method,
                "request_id": request_id,
                "correlation_id": correlation_id,
            },
        )
        return response

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    _record_http_metrics(request, response.status_code, time.perf_counter() - start)
    logger.info(
        "request.received",
        extra={
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
            "correlation_id": correlation_id,
        },
    )
    return response


def _record_http_metrics(request: Request, status_code: int, duration: float) -> None:
    from .observability.metrics import http_requests_total, http_request_duration_seconds
    try:
        path = request.url.path
        method = request.method
        http_requests_total.labels(method=method, path=path, status_code=str(status_code)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
    except Exception:
        pass

