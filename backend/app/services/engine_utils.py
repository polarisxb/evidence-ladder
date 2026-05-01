"""Shared utilities for attack engines (TAP, PAIR, IRIS, Crescendo)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable


async def should_stop_check(
    should_stop: Callable[[], bool | Awaitable[bool]] | None,
) -> bool:
    """Unified stop-check used by all attack engines.

    Returns True if the caller-supplied stop function indicates
    the scan should be aborted.
    """
    if should_stop is None:
        return False
    value = should_stop()
    if inspect.isawaitable(value):
        value = await value
    return bool(value)
