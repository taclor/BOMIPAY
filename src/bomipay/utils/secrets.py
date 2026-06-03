"""Secret masking utilities for safe logging and serialisation."""
from __future__ import annotations

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"password", "secret", "token", "api_key", "key", "authorization", "credential"}
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
