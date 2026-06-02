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

configure_logging()
logger = logging.getLogger("bomipay")

@asynccontextmanager
def lifespan(app: FastAPI):
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(merchant_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
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


