from __future__ import annotations

import re

import httpx

_SENSITIVE_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9]{2})[a-zA-Z0-9]{20,}"),
    re.compile(r"(key-[a-zA-Z0-9]{2})[a-zA-Z0-9]{20,}"),
    re.compile(r"(Bearer\s+[a-zA-Z0-9]{4})[a-zA-Z0-9]{20,}"),
]


def sanitize_error(error: Exception) -> str:
    """Return a non-empty, redacted error summary suitable for persistence/UI."""
    msg = str(error).strip()

    if not msg:
        if isinstance(error, httpx.TimeoutException):
            msg = "Request timed out"
        else:
            msg = error.__class__.__name__

    if msg == error.__class__.__name__:
        return msg

    for pattern in _SENSITIVE_PATTERNS:
        msg = pattern.sub(r"\1***REDACTED***", msg)

    return msg
