"""Secret masking utilities for safe logging and serialisation."""
from __future__ import annotations

import re

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"password", "secret", "token", "api_key", "key", "authorization", "credential", "bearer", "access_token", "refresh_token"}
)

_MASK = "***REDACTED***"


def mask_dict(d: dict) -> dict:
    """Return a shallow-copy of *d* with sensitive values replaced by ``***REDACTED***``.

    Recurses into nested :class:`dict` values.  Lists and other iterables are
    not traversed — only dict-of-dict structures are handled.
    """
    result: dict = {}
    for k, v in d.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            result[k] = _MASK
        elif isinstance(v, dict):
            result[k] = mask_dict(v)
        else:
            result[k] = v
    return result


def mask_account_number(number: str) -> str:
    """Return *number* with all but the last four digits replaced by ``****``.

    Examples::

        >>> mask_account_number("1234567890")
        '****7890'
        >>> mask_account_number("1234")
        '****1234'
    """
    if not number:
        return number
    last4 = number[-4:]
    return f"****{last4}"


def mask_email(email: str) -> str:
    """Return *email* with parts redacted.

    Examples::

        >>> mask_email("user@example.com")
        'u***@e***.com'
    """
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    masked_local = local[0] + "***" if local else "***"
    if "." in domain:
        parts = domain.split(".", 1)
        masked_domain = parts[0][0] + "***." + parts[1]
    else:
        masked_domain = domain[0] + "***"
    return f"{masked_local}@{masked_domain}"


def mask_bearer_token(token: str) -> str:
    """Return bearer token with only first 10 chars visible.

    Examples::

        >>> mask_bearer_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        'eyJhbGciOi***'
    """
    if not token or len(token) <= 10:
        return "***"
    return token[:10] + "***"
