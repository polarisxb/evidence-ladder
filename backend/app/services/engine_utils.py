"""Shared utilities for attack engines (TAP, PAIR, IRIS, Crescendo)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from app.config import settings
from app.services.latency_tracker import observed_latency_s


def scaled_timeout(base_s: float) -> float:
    """Size a per-call attack-engine timeout for the current target's speed.

    The engines hardcode short timeouts tuned for fast models. Slow or
    reasoning-style target/relay models routinely exceed them, which silently
    degrades multi-turn attacks (skipped turns, empty branches) and biases ASR
    downward. We pick the timeout from two sources and take the larger:

    * **Adaptive** (default on): derive a multiplier from the model's observed
      round-trip latency, ``observed / reference``, so a fast model keeps the
      base timeout and a slow one grows proportionally. Until a latency has
      been observed the factor is 1.0, i.e. unchanged.
    * **Manual floor**: ``attack_timeout_multiplier`` (default 1.0) acts as a
      lower bound / override for operators who want to force extra headroom.

    The combined factor is capped by ``attack_timeout_max_factor`` so a stuck
    call's latency can never inflate timeouts without bound. The result is
    never shorter than ``base_s``.
    """
    manual = settings.attack_timeout_multiplier
    factor = manual if (manual and manual > 0) else 1.0

    if settings.attack_timeout_adaptive:
        reference = settings.attack_timeout_reference_latency_s
        observed = observed_latency_s()
        if observed > 0 and reference > 0:
            auto = observed / reference
            if auto > factor:
                factor = auto

    cap = settings.attack_timeout_max_factor
    if cap and cap > 0:
        factor = min(factor, cap)
    if factor < 1.0:
        factor = 1.0
    return base_s * factor


# Typographic apostrophes/quotes that LLM output frequently uses instead of
# ASCII ones (e.g. gpt-style relays emit U+2019 in "I can't"). Refusal patterns
# are authored with plain ASCII quotes, so without this normalization a clear
# refusal evades detection — inflating the engines' preliminary ``success``
# flag and, for FITD/Crescendo, making them stop escalating against a target
# that actually refused. Mapping these to ASCII makes detection robust without
# adding any new refusal patterns (so it cannot create new false positives).
_QUOTE_TRANSLATION = {
    0x2018: "'",  # left single quotation mark
    0x2019: "'",  # right single quotation mark
    0x02BC: "'",  # modifier letter apostrophe
    0x2032: "'",  # prime
    0xFF07: "'",  # fullwidth apostrophe
    0x201C: '"',  # left double quotation mark
    0x201D: '"',  # right double quotation mark
}


def normalize_refusal_text(text: str) -> str:
    """Fold typographic quotes/apostrophes to ASCII for robust refusal matching."""
    if not text:
        return text
    return text.translate(_QUOTE_TRANSLATION)


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
