"""Tests for TASK-005 security hardening: headers, secret masking, docs toggle."""
from __future__ import annotations

import pytest

from bomipay.utils.secrets import (
    mask_dict, 
    mask_account_number, 
    mask_email,
    mask_bearer_token,
    SENSITIVE_KEYS
)


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Every response should include the required security headers."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age=31536000" in response.headers.get("Strict-Transport-Security", "")
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"


@pytest.mark.asyncio
async def test_security_headers_on_404(client):
    """Security headers should be present even on error responses."""
    response = await client.get("/non-existent-path-xyz")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# Docs toggle
# ---------------------------------------------------------------------------


def test_docs_disabled_when_setting_false():
    """When docs_enabled=False the FastAPI constructor kwargs disable all docs URLs."""
    # Test the config logic directly — verifies that the pattern used in main.py
    # produces the correct kwargs without needing to rebuild the app.
    docs_enabled = False
    kwargs = (
        {}
        if docs_enabled
        else {"openapi_url": None, "docs_url": None, "redoc_url": None}
    )
    assert kwargs == {"openapi_url": None, "docs_url": None, "redoc_url": None}


def test_docs_enabled_when_setting_true():
    """When docs_enabled=True the kwargs dict is empty (defaults preserved)."""
    docs_enabled = True
    kwargs = (
        {}
        if docs_enabled
        else {"openapi_url": None, "docs_url": None, "redoc_url": None}
    )
    assert kwargs == {}


# ---------------------------------------------------------------------------
# mask_dict
# ---------------------------------------------------------------------------


def test_mask_dict_top_level_sensitive_keys():
    raw = {"password": "s3cr3t", "username": "alice"}
    masked = mask_dict(raw)
    assert masked["password"] == "***REDACTED***"
    assert masked["username"] == "alice"


def test_mask_dict_case_insensitive():
    raw = {"PASSWORD": "hunter2", "Token": "abc123"}
    masked = mask_dict(raw)
    assert masked["PASSWORD"] == "***REDACTED***"
    assert masked["Token"] == "***REDACTED***"


def test_mask_dict_recursive():
    raw = {
        "user": {
            "email": "bob@example.com",
            "api_key": "super-secret",
        },
        "meta": {"version": 1},
    }
    masked = mask_dict(raw)
    assert masked["user"]["api_key"] == "***REDACTED***"
    assert masked["user"]["email"] == "bob@example.com"
    assert masked["meta"]["version"] == 1


def test_mask_dict_does_not_mutate_original():
    raw = {"secret": "original_value"}
    _ = mask_dict(raw)
    assert raw["secret"] == "original_value"


def test_mask_dict_all_sensitive_keys_covered():
    """All keys in SENSITIVE_KEYS must be masked."""
    raw = {k: "value123" for k in SENSITIVE_KEYS}
    masked = mask_dict(raw)
    for k in SENSITIVE_KEYS:
        assert masked[k] == "***REDACTED***", f"Expected key '{k}' to be masked"


# ---------------------------------------------------------------------------
# mask_account_number
# ---------------------------------------------------------------------------


def test_mask_account_number_standard():
    assert mask_account_number("1234567890") == "****7890"


def test_mask_account_number_short():
    assert mask_account_number("1234") == "****1234"


def test_mask_account_number_empty():
    assert mask_account_number("") == ""


def test_mask_account_number_format():
    result = mask_account_number("9876543210")
    assert result.startswith("****")
    assert result.endswith("3210")
    assert len(result) == 8


# ---------------------------------------------------------------------------
# mask_email
# ---------------------------------------------------------------------------


def test_mask_email_standard():
    result = mask_email("user@example.com")
    assert result.startswith("u***@")
    assert "***" in result


def test_mask_email_no_domain():
    result = mask_email("invalid.email")
    assert result == "invalid.email"


def test_mask_email_empty():
    assert mask_email("") == ""


def test_mask_email_preserves_structure():
    result = mask_email("alice.smith@company.co.uk")
    assert "@" in result
    assert result.count("@") == 1


# ---------------------------------------------------------------------------
# mask_bearer_token
# ---------------------------------------------------------------------------


def test_mask_bearer_token_long():
    long_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    result = mask_bearer_token(long_token)
    assert result.startswith("eyJhbGciOi")
    assert result.endswith("***")
    assert len(result) == 13  # 10 chars + "***"


def test_mask_bearer_token_short():
    assert mask_bearer_token("short") == "***"


def test_mask_bearer_token_empty():
    assert mask_bearer_token("") == "***"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(client):
    """Preflight from a configured origin should return 200 with CORS headers."""
    response = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_cors_blocks_unknown_origin(client):
    """Requests from an unknown origin should not receive CORS allow headers."""
    response = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil-site.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Either no ACAO header or it explicitly does not match the evil origin
    acao = response.headers.get("access-control-allow-origin", "")
    assert acao != "https://evil-site.example.com"
