"""Per-case baseline health probe.

Purpose
-------
When a case's primary response is classified as ``not_evaluable`` due to
a transport-layer failure (HTTP 5xx, adapter error, gateway HTML, etc.),
we still cannot tell from that one data point alone whether:

* the target as a whole is down (every subsequent case will also fail), or
* the target is alive but THIS particular payload caused the target's
  business layer to throw (which is itself a valuable attack signal).

This module issues a short benign probe (``"hello"`` with a 5s timeout)
against the same ``target_url`` / adapter the scan is using, caches the
result for a short TTL per ``task_id``, and returns a dict the caller
can attach to ``response_evaluation.baseline_probe``. The UI uses the
``status`` field to refine the "transport failure" label into either
"target online, payload triggered business error" or "target offline".

Design notes
------------
* **Same transport stack**: we deliberately call
  ``invoke_target_with_envelope`` so the probe hits the same adapter /
  custom compat wrapper the scan uses. A raw ``httpx.get("/health")``
  would tell us the host is reachable but not whether the whole chat
  pipeline works.
* **Tight TTL**: 30 seconds. Long enough that a burst of failing cases
  shares one probe, short enough that a flaky target doesn't freeze the
  label on a stale verdict.
* **Per-task lock**: prevents thundering-herd probes from several
  in-flight cases racing into the probe path simultaneously.
* **Never raises**: the probe always returns a dict so callers can
  unconditionally attach the result without wrapping every call site in
  try/except.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from app.services.response_screening import TargetResponseEnvelope
from app.services.target_client import invoke_target_with_envelope

logger = logging.getLogger(__name__)


BASELINE_PROBE_PROMPT = "hello"
BASELINE_PROBE_TIMEOUT_S = 5.0
BASELINE_PROBE_TTL_S = 30.0

# ``invalid_reason`` values that legitimately indicate a transport-layer
# failure and therefore warrant a baseline probe to disambiguate "target
# offline" from "payload triggered business exception". The A-class
# reasons ``known_fallback`` / ``configured_origin_rule`` (target
# actively returned a fallback template) and ``empty_response`` (often
# paired with HTTP 200 after fix A lands — target is clearly alive)
# deliberately DO NOT trigger a probe: they'd burn API quota for no
# classification gain.
BASELINE_PROBE_TRIGGER_REASONS: frozenset[str] = frozenset({
    "transport_error",
    "adapter_error",
    "http_error",
    "extract_error",
    "execution_error",
    "html_error",
})


_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _reset_cache_for_tests() -> None:
    """Test helper — not for production callers."""
    _cache.clear()
    _locks.clear()


def _envelope_is_healthy(envelope: TargetResponseEnvelope) -> bool:
    """Decide whether a probe envelope represents a reachable target.

    We treat 2xx as healthy even if the body is empty or looks like a
    refusal: the point of the probe is "did the HTTP/adapter layer
    complete at all", not "did the model cooperate". If the target's
    system prompt happens to refuse the word ``hello``, that still
    means the target service is up and talking to us.
    """
    if not envelope.transport_ok:
        return False
    status = envelope.http_status
    if status is None:
        # No HTTP status means either a direct-model transport that
        # doesn't carry one (openai_compatible / builtin) or a probe
        # that never reached the wire. Treat as healthy ONLY when we
        # got a non-empty response back without an error marker.
        if envelope.response_error:
            return False
        text = (envelope.response_text or "").strip()
        return bool(text)
    return 200 <= int(status) < 300


async def _run_probe(task) -> dict[str, Any]:
    case_id = f"baseline_{uuid.uuid4().hex[:8]}"
    try:
        envelope = await asyncio.wait_for(
            invoke_target_with_envelope(
                task,
                BASELINE_PROBE_PROMPT,
                case_id=case_id,
                variant_type="baseline_probe",
            ),
            timeout=BASELINE_PROBE_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        return {
            "status": "failed",
            "reason": f"probe_timeout_{int(BASELINE_PROBE_TIMEOUT_S)}s",
            "http_status": None,
            "probed_at": _iso_now(),
        }
    except Exception as exc:  # defensive: anything unexpected still returns a dict
        logger.warning("baseline probe for task=%s raised: %s", getattr(task, "id", "?"), exc)
        return {
            "status": "failed",
            "reason": str(exc)[:200],
            "http_status": None,
            "probed_at": _iso_now(),
        }

    if _envelope_is_healthy(envelope):
        return {
            "status": "ok",
            "reason": None,
            "http_status": envelope.http_status,
            "probed_at": _iso_now(),
        }
    reason = (envelope.response_error or "").strip() or "non_2xx_or_transport_fail"
    return {
        "status": "failed",
        "reason": reason[:200],
        "http_status": envelope.http_status,
        "probed_at": _iso_now(),
    }


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def get_cached_baseline_probe(
    task,
    *,
    ttl_s: float = BASELINE_PROBE_TTL_S,
    now: float | None = None,
) -> dict[str, Any]:
    """Return a cached baseline probe result, running a new probe on miss.

    The probe result is a dict with keys:
    * ``status``  — ``"ok"`` | ``"failed"``
    * ``reason``  — optional human-readable failure reason
    * ``http_status`` — HTTP status from the probe envelope, if any
    * ``probed_at`` — ISO timestamp when the probe actually ran
    * ``cached``  — ``True`` if served from cache, ``False`` if freshly run

    Never raises — on any error returns ``{"status": "failed", ...}``.
    """
    task_id = str(getattr(task, "id", "")) or "_unknown_"
    clock = time.monotonic if now is None else (lambda: now)  # type: ignore[assignment]
    current = clock()

    cached = _cache.get(task_id)
    if cached and cached[0] > current:
        return {**cached[1], "cached": True}

    lock = _locks.setdefault(task_id, asyncio.Lock())
    async with lock:
        cached = _cache.get(task_id)
        if cached and cached[0] > current:
            return {**cached[1], "cached": True}
        result = await _run_probe(task)
        _cache[task_id] = (current + ttl_s, result)
        return {**result, "cached": False}
