"""Rate limiting middleware for BomiPay API.

Per-path limits (applied only in production/staging):
  - Auth endpoints      (/api/v1/auth/*)    : 10  req/min per IP
  - Webhook endpoints   (/webhooks/*)       : 100 req/min per IP
  - AI endpoints        (/api/v1/ai*)       : 20  req/min per IP
  - Default                                 : 200 req/min per IP

Rate limiting is disabled in development and test environments to keep tests
fast and deterministic.  Set RATE_LIMIT_ENABLED=false to disable at runtime.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..config import settings

# ---------------------------------------------------------------------------
# Path-based limits: (max_requests, window_seconds)
# ---------------------------------------------------------------------------
_PATH_LIMITS: list[tuple[str, int, int]] = [
    ("/api/v1/auth/", 10, 60),
    ("/webhooks/", 100, 60),
    ("/api/v1/ai", 20, 60),
]
_DEFAULT_LIMIT = (200, 60)


def _get_limit(path: str) -> tuple[int, int]:
    for prefix, max_req, window in _PATH_LIMITS:
        if path.startswith(prefix):
            return max_req, window
    return _DEFAULT_LIMIT


class _RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window in-memory rate limiter keyed by (ip, path-prefix)."""

    def __init__(self, app) -> None:
        super().__init__(app)
        # {key: [timestamp, ...]}
        self._store: dict[str, list[float]] = defaultdict(list)

    def _bucket_key(self, request: Request) -> str:
        ip = (request.client.host if request.client else "unknown")
        path = request.url.path
        for prefix, _, _ in _PATH_LIMITS:
            if path.startswith(prefix):
                return f"{ip}:{prefix}"
        return f"{ip}:default"

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        max_requests, window = _get_limit(path)
        key = self._bucket_key(request)
        now = time.monotonic()

        timestamps = self._store[key]
        # Evict timestamps outside the current window
        cutoff = now - window
        self._store[key] = [t for t in timestamps if t > cutoff]

        if len(self._store[key]) >= max_requests:
            return Response(
                content='{"error":{"code":"RATE_LIMITED","message":"Too many requests. Please slow down."}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window)},
            )

        self._store[key].append(now)
        return await call_next(request)


def setup_rate_limiting(app) -> None:
    """Wire rate-limiting middleware into *app*.

    No-op when rate limiting is disabled or the environment is not
    production / staging (guards test suites and local dev).
    """
    if not settings.rate_limit_enabled:
        return
    if settings.environment not in ("production", "staging"):
        return

    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: F401
        from slowapi.errors import RateLimitExceeded  # noqa: F401
        from slowapi.util import get_remote_address  # noqa: F401

        limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    except ImportError:
        pass  # slowapi optional — fall back to built-in middleware

    app.add_middleware(_RateLimitMiddleware)
