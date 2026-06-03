import asyncio
import logging
import time
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from ..config import settings

router = APIRouter(tags=["health"])
logger = logging.getLogger("bomipay.health")

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    success: bool = True
    status: str = "ok"
    version: str = APP_VERSION


class LivenessResponse(BaseModel):
    status: str = "ok"


class DepsResponse(BaseModel):
    db: str
    redis: str
    details: dict


async def _check_db() -> tuple[str, dict]:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    start = time.perf_counter()
    try:
        # Use a short-lived engine with NullPool so the connection is immediately
        # closed after the check — avoids leaving pooled connections in the global
        # engine that cannot be cleaned up during event-loop teardown in tests.
        check_engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with check_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await check_engine.dispose()
        latency = round((time.perf_counter() - start) * 1000, 2)
        return "ok", {"latency_ms": latency}
    except Exception as exc:
        return "error", {"error": str(exc)}


async def _check_redis() -> tuple[str, dict]:
    """
    Probe Redis reachability via a plain TCP connection.

    Uses ``asyncio.timeout`` (Python 3.11+) instead of ``asyncio.wait_for``
    to avoid stale timer handles that prevent the event loop from closing in
    tests when the connection is refused/times out.
    """
    start = time.perf_counter()
    writer: asyncio.StreamWriter | None = None
    try:
        parsed = urlparse(settings.redis_url)
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 6379)
        async with asyncio.timeout(1.0):
            _, writer = await asyncio.open_connection(host, port)
        latency = round((time.perf_counter() - start) * 1000, 2)
        return "ok", {"latency_ms": latency}
    except Exception as exc:
        return "error", {"error": type(exc).__name__}
    finally:
        if writer is not None:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


@router.get("/health", response_model=HealthResponse, summary="Basic liveness")
async def health_check() -> HealthResponse:
    return HealthResponse()


@router.get("/health/live", response_model=LivenessResponse, summary="Liveness probe")
async def health_live() -> LivenessResponse:
    return LivenessResponse()


@router.get("/health/ready", summary="Readiness probe")
async def health_ready():
    from fastapi import Response
    import json

    db_status, _ = await _check_db()
    redis_status, _ = await _check_redis()

    ready = db_status == "ok"  # DB is the critical dependency
    status_code = 200 if ready else 503
    body = {"status": "ready" if ready else "not_ready", "db": db_status, "redis": redis_status}
    return Response(
        content=json.dumps(body),
        status_code=status_code,
        media_type="application/json",
    )


@router.get("/health/deps", response_model=DepsResponse, summary="Dependency health")
async def health_deps() -> DepsResponse:
    db_status, db_details = await _check_db()
    redis_status, redis_details = await _check_redis()
    return DepsResponse(
        db=db_status,
        redis=redis_status,
        details={"db": db_details, "redis": redis_details},
    )
