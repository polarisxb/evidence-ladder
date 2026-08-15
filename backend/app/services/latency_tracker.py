"""Process-global observed LLM-call latency, used to adapt attack-engine
per-call timeouts to the target/relay model's real speed.

Why
---
The multi-turn engines (crescendo/tap/pair/msj/fitd/ice/iris) cap each
attacker/judge LLM call with a short, hardcoded per-call timeout tuned for
fast models (~12s). A *static* multiplier (``attack_timeout_multiplier``)
lets an operator widen those timeouts for slow models, but it is not
adaptive: set it for a slow model and it stays too generous if you later
point the scan at a fast one.

This module records the round-trip time of every successful scheduler call
into a smoothed estimate (EWMA). ``engine_utils.scaled_timeout`` reads that
estimate to size timeouts automatically: fast models keep the estimate small
(timeouts stay at their fast defaults), slow/reasoning models push it up
(timeouts grow proportionally, bounded by a hard factor cap). No manual knob
required, and the estimate never *shortens* a timeout below its base.

The estimate is a deliberately simple single global EWMA: in practice the
attacker/judge/target calls being timed share one relay endpoint, so a single
smoothed latency is a good proxy. It is reset between tests via
``reset_for_tests``.
"""
from __future__ import annotations

import threading

# Weight of the newest sample. Higher == reacts faster to a model's speed,
# lower == steadier. 0.3 settles within a handful of calls.
_ALPHA = 0.3

_lock = threading.Lock()
_ewma_s: float = 0.0


def record_latency(seconds: float) -> None:
    """Feed one observed successful-call round-trip time (seconds) into the EWMA.

    Non-positive or absurd values are ignored so a stuck/near-timeout call
    cannot poison the estimate.
    """
    global _ewma_s
    if not seconds or seconds <= 0:
        return
    with _lock:
        if _ewma_s <= 0:
            _ewma_s = seconds
        else:
            _ewma_s = (1.0 - _ALPHA) * _ewma_s + _ALPHA * seconds


def observed_latency_s() -> float:
    """Return the smoothed observed call latency in seconds (0.0 if unknown)."""
    with _lock:
        return _ewma_s


def reset_for_tests() -> None:
    """Test helper — clears the global estimate. Not for production callers."""
    global _ewma_s
    with _lock:
        _ewma_s = 0.0
