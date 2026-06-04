"""Security headers middleware for BomiPay API.

Adds the following headers to every response:
  - X-Content-Type-Options
  - X-Frame-Options
  - X-XSS-Protection
  - Strict-Transport-Security (HSTS)
  - Referrer-Policy
  - Permissions-Policy
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects standard security headers into every HTTP response."""

    def _get_security_headers(self) -> dict[str, str]:
        """Build security headers dict using configured values."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": f"max-age={settings.hsts_max_age}; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        headers = self._get_security_headers()
        for header, value in headers.items():
            response.headers.setdefault(header, value)
        return response


def setup_security_headers(app) -> None:
    """Register :class:`SecurityHeadersMiddleware` with *app*."""
    app.add_middleware(SecurityHeadersMiddleware)
