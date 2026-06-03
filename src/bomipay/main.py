import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging import configure_logging
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service.startup", extra={"environment": settings.environment})
    yield
    logger.info("service.shutdown")

app = FastAPI(
    title="Bomi Pay API",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Paystack-Signature"],
)

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


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request.received",
        extra={
            "path": request.url.path,
            "method": request.method,
            "request_id": request_id,
        },
    )
    return response


