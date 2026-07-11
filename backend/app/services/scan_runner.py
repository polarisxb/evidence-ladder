"""Orchestrates the full scan workflow: load templates -> execute attacks -> analyze -> score.

This module is the top-level orchestration layer only.
Target communication   -> app.services.target_client
Case execution/probe   -> app.services.case_executor
DB persistence         -> app.services.case_persistence
"""

import asyncio
import logging
import uuid
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timezone
from pathlib import Path

from fastapi import WebSocket
from sqlalchemy import select, update
from app.database import async_session
from app.models import AttackResult, ScanTask
from app.services.adapter_executor import resolve_task_adapter_payload
from app.services.attack_engine import AttackEngine
from app.services.llm_client import (
    _scan_judge_provider_id,
    _scan_judge_model,
    _scan_generation_provider_id,
    _scan_generation_model,
)
from app.services.crescendo_engine import run_crescendo
from app.services.fitd_engine import run_fitd
from app.services.msj_engine import run_msj
from app.services.ice_engine import run_ice
from app.services.tap_engine import run_tap
from app.services.pair_engine import run_pair
from app.services.iris_engine import run_iris
from app.services.mutation_engine import generate_variants
from app.services.risk_scorer import compute_overall_score, classify_overall_risk
from app.services.response_screening import (
    TargetResponseEnvelope,
    describe_not_evaluable_reason,
    origin_rules_from_target_config,
    response_evaluation_payload,
    screen_response_origin,
)
from app.services.target_client import (
    invoke_target_with_envelope as _invoke_target_with_envelope,
    send_to_target_with_result as _send_to_target_with_result,
)
from app.services.case_executor import (
    prepare_case_attempt as _prepare_case_attempt,
    prepare_explicit_case_attempt as _prepare_explicit_case_attempt,
    matched_probe_session_id as _matched_probe_session_id,
    build_attack_objective as _build_attack_objective,
    envelope_to_variant_transport_meta as _envelope_to_variant_transport_meta,
)
from app.services.error_utils import sanitize_error
from app.services.case_persistence import (
    persist_case_with_legacy_result as _persist_case_with_legacy_result,
)
from app.services.retest_orchestrator import (
    resolve_retest_arm as _resolve_retest_arm,
    run_case_retest as _run_case_retest,
    persist_case_retest_lineage as _persist_case_retest_lineage,
)
from app.services.finding_classifier import is_confirmed_finding
from app.services.quartet_generator import load_suite

logger = logging.getLogger(__name__)
ACTIVE_SCAN_STATUSES = {"pending", "running"}


def _apply_scan_providers(task: ScanTask) -> None:
    """Set per-scan provider overrides from the task's stored provider IDs and models."""
    judge_id = getattr(task, "judge_provider_id", None)
    judge_model = getattr(task, "judge_model", None)
    gen_id = getattr(task, "generation_provider_id", None)
    gen_model = getattr(task, "generation_model", None)
    if judge_id:
        _scan_judge_provider_id.set(judge_id)
    if judge_model:
        _scan_judge_model.set(judge_model)
    if gen_id:
        _scan_generation_provider_id.set(gen_id)
    if gen_model:
        _scan_generation_model.set(gen_model)
MAX_SCAN_DURATION_S = 3600.0  # 全局扫描超时 1 小时
_MAX_CONCURRENT_CHAINS = 8   # 全局最大并行攻击链数

# Per-scan stop signaling — avoids a DB query on every template/payload check.
# stop event is set either by signal_scan_stop() (cancel API) or by the TTL
# DB poll when it detects the task is no longer active.
_scan_stop_events: dict[str, asyncio.Event] = {}
_scan_stop_check_ts: dict[str, float] = {}  # task_id -> last DB-poll monotonic time
_STOP_CHECK_DB_INTERVAL_S: float = 5.0      # max DB poll frequency per scan
_SCAN_HEALTH_PROBE_PROMPTS = ("hello", "what can you help me with")
_SCAN_HEALTH_WINDOW_SIZE = 10
_SCAN_HEALTH_INVALID_THRESHOLD = 8
# Runtime health has two tiers:
# - ``signature_streak`` (5) consecutive non-evaluable responses → ``degraded``
#   Banner only: scan keeps running, each failing case is recorded as
#   not_evaluable by response_screening (which prevents fake defense_success).
# - ``unhealthy_streak`` (20) consecutive → ``unhealthy``
#   Dead-man switch: target is clearly down, stop the scan to avoid
#   wasting attempts on a target that won't respond.
_SCAN_HEALTH_SIGNATURE_STREAK_THRESHOLD = 5
_SCAN_HEALTH_UNHEALTHY_STREAK_THRESHOLD = 20
# Recovery: if the target has produced this many consecutive evaluable
# responses while the scan is in ``degraded`` state, downgrade back to
# ``healthy`` and clear the stale failure reason. Without this, the UI
# freezes at the trigger snapshot forever (e.g. "100% invalid ratio")
# even after the target has long recovered, which looks indistinguishable
# from a hung scan to the user.
_SCAN_HEALTH_RECOVERY_STREAK_THRESHOLD = 3
_scan_health_trackers: dict[str, dict] = {}
_db_write_lock: asyncio.Lock | None = None
_db_write_lock_loop_id: int | None = None


def _get_db_write_lock() -> asyncio.Lock:
    global _db_write_lock, _db_write_lock_loop_id
    loop_id = id(asyncio.get_running_loop())
    if _db_write_lock is None or _db_write_lock_loop_id != loop_id:
        _db_write_lock = asyncio.Lock()
        _db_write_lock_loop_id = loop_id
    return _db_write_lock


def signal_scan_stop(task_id: str) -> None:
    """Immediately signal an in-progress scan to stop (e.g. from cancel API)."""
    evt = _scan_stop_events.get(task_id)
    if evt is not None:
        evt.set()


async def _broadcast(ws_clients: dict[str, list[WebSocket]], task_id: str, data: dict):
    clients = ws_clients.get(task_id)
    if not clients:
        return
    snapshot = list(clients)
    dead: list[WebSocket] = []
    for ws in snapshot:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    if dead:
        for ws in dead:
            try:
                clients.remove(ws)
            except ValueError:
                pass
        if not clients and task_id in ws_clients:
            del ws_clients[task_id]


def _entry_text(entry, field: str) -> str:
    value = entry.get(field) if isinstance(entry, dict) else getattr(entry, field, None)
    return value if isinstance(value, str) and value.strip() else ""


def _last_non_empty(entries: list | None, field: str) -> str:
    if not entries:
        return ""
    for entry in reversed(entries):
        value = _entry_text(entry, field)
        if value:
            return value
    return ""


def _record_envelope_attempt(
    probe_attempts: list[dict],
    prompt: str,
    envelope: TargetResponseEnvelope,
) -> str:
    """Record one send_fn invocation including the full envelope.

    The advanced engines (TAP, PAIR, IRIS, Crescendo, FITD, MSJ, ICE) only
    propagate a ``str`` response through their internal search tree, which
    would drop ``http_status`` / ``content_type`` / ``transport_ok`` on the
    floor. Storing the envelope alongside the flattened response string
    lets us recover the metadata at case-persistence time via
    ``_resolve_envelope_for_response`` so ``screen_response_origin`` sees
    an accurate HTTP picture (e.g. "200 with empty body" vs "no HTTP call
    at all"), which is the difference between ``model silence`` and
    ``transport failure`` in the UI.

    Returns the flattened response string that the engine should treat as
    the target reply.
    """
    response_text = str(envelope.response_text or "")
    if envelope.response_error and not response_text:
        response_text = f"[ERROR] {envelope.response_error}"
    probe_attempts.append({
        "prompt": prompt,
        "response": response_text,
        "session_id": envelope.session_id,
        "envelope": envelope,
    })
    return response_text


def _resolve_envelope_for_response(
    probe_attempts: list[dict],
    resolved_response: str,
) -> TargetResponseEnvelope | None:
    """Find the envelope that produced ``resolved_response``.

    Preference order:
    1. Latest attempt whose flattened response exactly matches.
    2. Last attempt overall (useful when the engine picked an empty
       response — we still want to surface its HTTP status so the UI
       can distinguish "200 + empty body" from "no response at all").
    """
    if not probe_attempts:
        return None
    if resolved_response:
        for attempt in reversed(probe_attempts):
            if attempt.get("response") == resolved_response:
                envelope = attempt.get("envelope")
                if isinstance(envelope, TargetResponseEnvelope):
                    return envelope
    last = probe_attempts[-1]
    envelope = last.get("envelope")
    return envelope if isinstance(envelope, TargetResponseEnvelope) else None


def _envelope_response_error(envelope: TargetResponseEnvelope | None) -> str | None:
    """Return the envelope's response_error if it has textual content."""
    if envelope is None:
        return None
    err = envelope.response_error
    if isinstance(err, str) and err.strip():
        return err
    return None


def _task_origin_rules(task) -> dict[str, list[str]] | None:
    target_config = getattr(task, "target_config", None)
    if not isinstance(target_config, dict):
        return None
    return origin_rules_from_target_config(target_config)


def _new_scan_health_tracker(adv: dict | None = None) -> dict:
    adv = adv or {}
    window_size = int(adv.get("health_window_size") or _SCAN_HEALTH_WINDOW_SIZE)
    invalid_threshold = int(adv.get("health_invalid_threshold") or _SCAN_HEALTH_INVALID_THRESHOLD)
    signature_streak = int(adv.get("health_signature_streak") or _SCAN_HEALTH_SIGNATURE_STREAK_THRESHOLD)
    unhealthy_streak = int(
        adv.get("health_unhealthy_streak") or _SCAN_HEALTH_UNHEALTHY_STREAK_THRESHOLD
    )
    recovery_streak = int(
        adv.get("health_recovery_streak") or _SCAN_HEALTH_RECOVERY_STREAK_THRESHOLD
    )
    return {
        "lock": asyncio.Lock(),
        "target_health": None,
        "health_probe_passed": None,
        "health_failure_reason": None,
        "recent_health_signature": None,
        "invalid_response_ratio": None,
        "recent_invalid_window": deque(maxlen=window_size),
        "window_size": window_size,
        "invalid_threshold": invalid_threshold,
        "signature_streak_threshold": signature_streak,
        "unhealthy_streak_threshold": unhealthy_streak,
        "recovery_streak_threshold": recovery_streak,
        "current_signature": None,
        "current_signature_streak": 0,
        # Consecutive evaluable responses. Used to downgrade
        # degraded → healthy once the target proves it is back.
        "current_valid_streak": 0,
    }


def _health_signature(response_evaluation: dict | None) -> str | None:
    payload = response_evaluation_payload(response_evaluation) or {}
    if payload.get("evaluation_validity") != "not_evaluable":
        return None
    for key in ("matched_signature", "invalid_reason", "response_origin"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "not_evaluable"


def _scan_health_snapshot(tracker: dict) -> dict:
    ratio = tracker.get("invalid_response_ratio")
    if isinstance(ratio, (int, float)):
        ratio = round(float(ratio), 3)
    return {
        "target_health": tracker.get("target_health"),
        "health_probe_passed": tracker.get("health_probe_passed"),
        "health_failure_reason": tracker.get("health_failure_reason"),
        "recent_health_signature": tracker.get("recent_health_signature"),
        "invalid_response_ratio": ratio,
    }


def _apply_scan_health_snapshot(task, snapshot: dict) -> None:
    task.target_health = snapshot.get("target_health")
    task.health_probe_passed = snapshot.get("health_probe_passed")
    task.health_failure_reason = snapshot.get("health_failure_reason")
    task.recent_health_signature = snapshot.get("recent_health_signature")
    task.invalid_response_ratio = snapshot.get("invalid_response_ratio")


async def _persist_scan_health_snapshot(task_id: str, snapshot: dict) -> None:
    async with _get_db_write_lock():
        async with async_session() as local_db:
            try:
                await local_db.execute(
                    update(ScanTask)
                    .where(ScanTask.id == task_id)
                    .values(
                        target_health=snapshot.get("target_health"),
                        health_probe_passed=snapshot.get("health_probe_passed"),
                        health_failure_reason=snapshot.get("health_failure_reason"),
                        recent_health_signature=snapshot.get("recent_health_signature"),
                        invalid_response_ratio=snapshot.get("invalid_response_ratio"),
                    )
                )
                await local_db.commit()
            except Exception:
                await local_db.rollback()
                raise


async def _broadcast_scan_health(ws_clients: dict[str, list[WebSocket]], task_id: str, snapshot: dict) -> None:
    await _broadcast(ws_clients, task_id, {
        "type": "scan_health",
        "target_health": snapshot.get("target_health"),
        "health_probe_passed": snapshot.get("health_probe_passed"),
        "health_failure_reason": snapshot.get("health_failure_reason"),
        "recent_health_signature": snapshot.get("recent_health_signature"),
        "invalid_response_ratio": snapshot.get("invalid_response_ratio"),
    })


async def probe_target_health(task) -> dict:
    origin_rules = _task_origin_rules(task)
    evaluations: list[dict] = []

    for prompt in _SCAN_HEALTH_PROBE_PROMPTS:
        try:
            envelope = await _invoke_target_with_envelope(
                task,
                prompt,
                case_id=f"health-probe-{uuid.uuid4()}",
                variant_type="health_probe",
            )
        except Exception as exc:
            envelope = TargetResponseEnvelope(
                response_text=None,
                response_error=sanitize_error(exc),
                response_status="failed",
                session_id=None,
                target_type=task.target_type,
                transport_ok=False,
                http_status=None,
                content_type=None,
                transport_meta={},
                response_origin="unknown",
                origin_confidence="low",
                evaluation_validity="evaluable",
            )
        evaluations.append(
            screen_response_origin(envelope, origin_rules=origin_rules).model_dump()
        )

    not_evaluable = [
        item for item in evaluations
        if item.get("evaluation_validity") == "not_evaluable"
    ]
    invalid_ratio = round(len(not_evaluable) / len(evaluations), 3) if evaluations else 0.0
    recent_signature = _health_signature(not_evaluable[-1]) if not_evaluable else None

    if not not_evaluable:
        return {
            "target_health": "healthy",
            "health_probe_passed": True,
            "health_failure_reason": None,
            "recent_health_signature": None,
            "invalid_response_ratio": invalid_ratio,
        }

    if len(not_evaluable) == len(evaluations):
        signatures = [signature for signature in (_health_signature(item) for item in not_evaluable) if signature]
        if signatures and len(signatures) == len(not_evaluable) and len(set(signatures)) == 1:
            return {
                "target_health": "unhealthy",
                "health_probe_passed": False,
                "health_failure_reason": (
                    "Health probe detected repeated non-evaluable benign responses. "
                    + describe_not_evaluable_reason(not_evaluable[0])
                ),
                "recent_health_signature": signatures[-1],
                "invalid_response_ratio": invalid_ratio,
            }

    return {
        "target_health": "degraded",
        "health_probe_passed": False,
        "health_failure_reason": (
            f"Health probe detected {len(not_evaluable)}/{len(evaluations)} non-evaluable benign responses. "
            + describe_not_evaluable_reason(not_evaluable[0])
        ),
        "recent_health_signature": recent_signature,
        "invalid_response_ratio": invalid_ratio,
    }


async def _observe_case_response_health(
    task_id: str,
    case_attempt: dict,
    ws_clients: dict[str, list[WebSocket]],
) -> None:
    response_evaluation = response_evaluation_payload(case_attempt.get("response_evaluation"))
    if response_evaluation is None:
        return

    tracker = _scan_health_trackers.get(task_id)
    if tracker is None:
        return

    async with tracker["lock"]:
        previous_snapshot = _scan_health_snapshot(tracker)
        window = tracker["recent_invalid_window"]
        signature = _health_signature(response_evaluation)
        is_invalid = signature is not None

        window.append(1 if is_invalid else 0)
        if is_invalid:
            tracker["recent_health_signature"] = signature
            tracker["current_valid_streak"] = 0
            if tracker.get("current_signature") == signature:
                tracker["current_signature_streak"] += 1
            else:
                tracker["current_signature"] = signature
                tracker["current_signature_streak"] = 1
        else:
            tracker["current_signature"] = None
            tracker["current_signature_streak"] = 0
            tracker["current_valid_streak"] = tracker.get("current_valid_streak", 0) + 1

        tracker["invalid_response_ratio"] = (
            round(sum(window) / len(window), 3) if window else 0.0
        )

        current_health = tracker.get("target_health") or "healthy"
        next_health = current_health
        next_reason = tracker.get("health_failure_reason")

        sig_streak_threshold = tracker.get("signature_streak_threshold", _SCAN_HEALTH_SIGNATURE_STREAK_THRESHOLD)
        unhealthy_streak_threshold = tracker.get(
            "unhealthy_streak_threshold", _SCAN_HEALTH_UNHEALTHY_STREAK_THRESHOLD
        )
        recovery_streak_threshold = tracker.get(
            "recovery_streak_threshold", _SCAN_HEALTH_RECOVERY_STREAK_THRESHOLD
        )
        win_size = tracker.get("window_size", _SCAN_HEALTH_WINDOW_SIZE)
        inv_threshold = tracker.get("invalid_threshold", _SCAN_HEALTH_INVALID_THRESHOLD)
        streak = tracker["current_signature_streak"]
        valid_streak = tracker["current_valid_streak"]

        if current_health != "unhealthy":
            # Tier 2 · dead-man switch: if degraded persisted and the streak
            # kept growing all the way to ``unhealthy_streak_threshold``,
            # upgrade to unhealthy. Evaluate this BEFORE the degraded rule
            # so a single event can jump straight from healthy → unhealthy
            # when the threshold is very low (used in tests).
            if signature and streak >= unhealthy_streak_threshold:
                next_health = "unhealthy"
                next_reason = (
                    f"Target emitted {streak} consecutive non-evaluable "
                    f"responses ({signature}); dead-man switch tripped."
                )
            elif (
                current_health == "degraded"
                and valid_streak >= recovery_streak_threshold
                and sum(window) <= max(1, inv_threshold // 4)
            ):
                # Recovery · target has produced enough consecutive
                # evaluable responses AND the recent-invalid window is
                # mostly clean. Downgrade to healthy and clear the stale
                # failure reason so the UI stops lying about "100% invalid".
                # We keep the dead-man switch asymmetric: once unhealthy
                # is reached the scan is stopped entirely, so there is no
                # recovery path out of unhealthy — that would re-introduce
                # the bug where a crashing target keeps getting probed.
                next_health = "healthy"
                next_reason = None
                tracker["recent_health_signature"] = None
            elif (
                streak >= sig_streak_threshold
                and signature
                and current_health == "healthy"
            ):
                # Tier 1 · banner only. Scan keeps running — each failing
                # case gets a not_evaluable record from response_screening,
                # which prevents fake defense_success in the final report.
                next_health = "degraded"
                next_reason = (
                    f"Repeated non-evaluable signature during scan: {signature} "
                    f"({streak} consecutive responses)."
                )
            elif (
                len(window) >= win_size
                and sum(window) >= inv_threshold
                and current_health == "healthy"
            ):
                next_health = "degraded"
                next_reason = (
                    f"High non-evaluable ratio during scan: {sum(window)}/{len(window)} recent responses."
                )

        tracker["target_health"] = next_health
        tracker["health_failure_reason"] = next_reason
        snapshot = _scan_health_snapshot(tracker)

    if snapshot == previous_snapshot:
        return

    await _persist_scan_health_snapshot(task_id, snapshot)

    # Always broadcast any snapshot change, not just target_health transitions.
    # Previously the UI only saw the moment a scan degraded and never saw the
    # target recover — so "100% invalid ratio" stayed frozen on screen even
    # after the target had long come back. Pushing every changed snapshot is
    # cheap (at most one per case) and keeps the banner in sync with reality.
    await _broadcast_scan_health(ws_clients, task_id, snapshot)

    prev_state = previous_snapshot.get("target_health")
    next_state = snapshot.get("target_health")
    if next_state != prev_state:
        if next_state == "degraded":
            # Banner only — do NOT stop the scan. response_screening will
            # mark each failing case as not_evaluable, so the final report
            # cannot contain fake defense_success entries driven by empty
            # or error responses.
            logger.warning(
                "Scan %s: runtime health DEGRADED; scan continues. reason=%s",
                task_id,
                snapshot.get("health_failure_reason"),
            )
        elif next_state == "unhealthy":
            logger.error(
                "Scan %s: runtime health UNHEALTHY — dead-man switch tripped, "
                "signalling scan stop. reason=%s",
                task_id,
                snapshot.get("health_failure_reason"),
            )
            signal_scan_stop(task_id)
        elif next_state == "healthy" and prev_state == "degraded":
            logger.info(
                "Scan %s: runtime health RECOVERED to healthy after previous "
                "degradation; stale failure reason cleared.",
                task_id,
            )


def _count_base_template_cases(template: dict) -> int:
    payloads = template.get("payloads", []) or []
    if template.get("multi_turn"):
        return 1 if payloads else 0
    return len(payloads)


def _is_vuln_case(case_attempt: dict) -> bool:
    """Return True iff the case should be counted in ``vulnerabilities_found``.

    Delegates to ``finding_classifier.is_confirmed_finding`` so the live
    scanner, ``scan_recovery``, posture metrics, and reports all agree on
    what counts as a finding. Only ``confirmed`` (hard evidence) and
    ``suspected`` (AI high-confidence) classes are counted — ``needs_review``
    is tracked separately in ``posture_metrics`` so reviewers see its bucket
    instead of having it inflate the headline vulnerability count.
    """
    return is_confirmed_finding(case_attempt)


async def _persist_and_count(
    task_id: str,
    task,
    tpl: dict,
    case_attempt: dict,
    analysis,
    **persist_kwargs,
) -> tuple[int, int, int]:
    """Persist results in an **isolated** session and atomically increment counters.

    Returns ``(completed_attacks, vulnerabilities_found, total_attacks)`` after
    the increment so callers can broadcast accurate progress without holding a
    shared DB session.

    Uses _db_write_lock to serialize SQLite writes and avoid 'database is locked'.
    """
    async with _get_db_write_lock():
        async with async_session() as local_db:
            try:
                await _persist_case_with_legacy_result(
                    local_db, task, tpl, case_attempt, auto_commit=False, **persist_kwargs,
                )
                vuln_delta = 1 if _is_vuln_case(case_attempt) else 0
                await local_db.execute(
                    update(ScanTask)
                    .where(ScanTask.id == task_id)
                    .values(
                        completed_attacks=ScanTask.completed_attacks + 1,
                        vulnerabilities_found=ScanTask.vulnerabilities_found + vuln_delta,
                    )
                )
                await local_db.commit()
            except Exception:
                await local_db.rollback()
                raise
            row = await local_db.execute(
                select(
                    ScanTask.completed_attacks,
                    ScanTask.vulnerabilities_found,
                    ScanTask.total_attacks,
                ).where(ScanTask.id == task_id)
            )
            c = row.one()
            counts = (c[0], c[1], c[2])
    # Run the ④ retest loop outside the write lock (it may issue target/probe
    # queries) then persist its lineage. Gated by the experiment arm in
    # advanced_config; a no-op for existing scans and never fails the case.
    await _maybe_persist_case_retest(task, tpl, case_attempt)
    return counts


async def _maybe_persist_case_retest(task, tpl: dict, case_attempt: dict) -> None:
    advanced = task.advanced_config if isinstance(task.advanced_config, dict) else {}
    resolved = _resolve_retest_arm(advanced, target_type=getattr(task, "target_type", None))
    if resolved is None:
        return
    arm, config = resolved
    try:
        lineage = await _run_case_retest(
            task=task, template=tpl, case_attempt=case_attempt, config=config
        )
    except Exception as exc:
        logger.warning(
            "Retest loop failed for case %s: %s", case_attempt.get("case_id"), exc
        )
        return
    reason = "; ".join(sorted(lineage.initial_conflict_types)) or None
    try:
        async with _get_db_write_lock():
            async with async_session() as local_db:
                await _persist_case_retest_lineage(
                    local_db,
                    task=task,
                    case_id=str(case_attempt.get("case_id") or ""),
                    arm=arm,
                    retest_reason=reason,
                    lineage=lineage,
                    auto_commit=True,
                )
    except Exception as exc:
        logger.warning(
            "Persisting retest lineage failed for case %s: %s",
            case_attempt.get("case_id"),
            exc,
        )


async def _increment_completed(task_id: str) -> None:
    """Bump completed_attacks by 1 without persisting a result row.

    Called from except blocks so that engine failures don't leave the
    counter behind, which would cause 'ended early' false positives.
    """
    try:
        async with _get_db_write_lock():
            async with async_session() as local_db:
                await local_db.execute(
                    update(ScanTask)
                    .where(ScanTask.id == task_id)
                    .values(completed_attacks=ScanTask.completed_attacks + 1)
                )
                await local_db.commit()
    except Exception:
        logger.debug("_increment_completed failed for %s (non-critical)", task_id)


_ENGINE_MAX_RETRIES = 1  # retry failed engine templates once


async def _gather_engine_tasks(
    task_id: str,
    process_fn: Callable[[dict], Awaitable[bool]],
    templates: list[dict],
    engine_name: str,
    sem: asyncio.Semaphore | None = None,
    max_retries: int = _ENGINE_MAX_RETRIES,
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    on_skip: Callable[[dict], Awaitable[None]] | None = None,
) -> None:
    """Run *process_fn* per template, retry failures, then count remaining.

    *process_fn* must return ``True`` iff it called ``_persist_and_count``
    (which already bumps ``completed_attacks``). Returning ``False`` signals a
    clean skip (``should_stop`` / empty payload / etc.).

    Counter alignment rule — we only bump ``completed_attacks`` for a skipped
    or failed template when **no scan-level stop signal is active**. When the
    scan was intentionally stopped (user cancel, runtime-health tracker,
    deadline), we leave the remaining templates uncounted so that the final
    ``completed_attacks < total_attacks`` correctly surfaces as ``failed`` /
    ``cancelled`` instead of pretending the scan ran to completion. Individual
    single-case glitches (no stop signal) are still counted so one flaky case
    can't fail the whole scan.

    ``on_skip`` is invoked once per template that we counted here without a
    ``_persist_and_count`` path (clean skip or retry-exhausted failure). It
    should clear the UI's in-flight tracker for that template — otherwise the
    frontend ``runningAttacks`` map holds on to the started template_id
    forever because ``process_fn`` broadcast ``attack_started`` but never
    got far enough to broadcast the matching ``attack_completed``.
    """

    async def _run(tpl: dict) -> bool:
        if sem:
            async with sem:
                return bool(await process_fn(tpl))
        return bool(await process_fn(tpl))

    async def _stop_active() -> bool:
        return bool(should_stop and await should_stop())

    async def _emit_skip(tpl: dict) -> None:
        if on_skip is None:
            return
        try:
            await on_skip(tpl)
        except Exception as exc:  # pragma: no cover — never let UI cleanup break counters
            logger.debug("%s on_skip failed for %s: %s", engine_name, tpl.get("id", "?"), exc)

    pool = list(templates[:5])
    remaining_budget = len(pool)  # count at most one +1 per template across retries
    for attempt in range(1 + max_retries):
        if not pool or await _stop_active():
            break
        results = await asyncio.gather(
            *[_run(tpl) for tpl in pool],
            return_exceptions=True,
        )
        stop_now = await _stop_active()
        failed = []
        for tpl, r in zip(pool, results):
            if isinstance(r, Exception):
                logger.warning(
                    "%s failed for %s (attempt %d/%d): %s",
                    engine_name, tpl.get("id", "?"),
                    attempt + 1, 1 + max_retries, r,
                )
                failed.append(tpl)
            elif r is False and remaining_budget > 0:
                # Clean skip. If the scan was intentionally stopped, do NOT
                # backfill the counter — let "ended early" propagate to the
                # final status. Otherwise (e.g. empty base_payload), count so
                # counters stay aligned and status = "completed".
                if not stop_now:
                    await _increment_completed(task_id)
                    await _emit_skip(tpl)
                remaining_budget -= 1
            elif r is True and remaining_budget > 0:
                # _persist_and_count already incremented; just consume budget
                # so a later retry-exhaustion sweep doesn't double-count.
                remaining_budget -= 1
        pool = failed  # narrow pool to only failures before checking
        if not pool:
            break
        if attempt < max_retries:
            logger.info(
                "%s: retrying %d failed template(s) after first pass",
                engine_name, len(pool),
            )

    # All retries exhausted. Count remaining failures only if the scan is still
    # active; otherwise an active stop signal means those templates were cut
    # short, and the scan SHOULD end as "failed" / "cancelled".
    if await _stop_active():
        return
    for tpl in pool:
        if remaining_budget <= 0:
            break
        await _increment_completed(task_id)
        await _emit_skip(tpl)
        remaining_budget -= 1


async def _check_should_stop_isolated(task_id: str, scan_deadline: float) -> bool:
    """Check stop condition using in-memory event + TTL-limited DB poll.

    Fast path: checks the in-memory asyncio.Event (no I/O).
    Slow path: polls the DB at most once every _STOP_CHECK_DB_INTERVAL_S seconds.
    """
    if asyncio.get_running_loop().time() >= scan_deadline:
        return True
    evt = _scan_stop_events.get(task_id)
    if evt is not None and evt.is_set():
        return True
    now = asyncio.get_running_loop().time()
    if now - _scan_stop_check_ts.get(task_id, 0.0) < _STOP_CHECK_DB_INTERVAL_S:
        return False
    _scan_stop_check_ts[task_id] = now
    async with async_session() as check_db:
        result = await check_db.execute(
            select(ScanTask.status).where(ScanTask.id == task_id)
        )
        status = result.scalar_one_or_none()
    should_stop = status not in ACTIVE_SCAN_STATUSES
    if should_stop and evt is not None:
        evt.set()
    return should_stop


async def _run_single_base_case(
    task_id: str,
    task,
    tpl: dict,
    payload_text: str,
    ws_clients: dict,
    *,
    quartet_mode: str,
    scan_deadline: float,
) -> None:
    """Execute one single-turn base attack case and persist results atomically.

    Uses ``persisted`` flag + ``try/finally`` so that a successful run is
    counted exactly once (via ``_persist_and_count``) and a single-case failure
    (no scan-level stop) is also counted so one flaky case can't fail the whole
    scan. When a scan-level stop is active (cancel / runtime-health tracker /
    deadline), we *do not* backfill the counter — that lets ``completed <
    total`` propagate to ``status = "failed"`` / ``"cancelled"`` and tells the
    user the scan was cut short instead of pretending it ran to completion.
    """
    persisted = False
    try:
        if await _check_should_stop_isolated(task_id, scan_deadline):
            return
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": tpl["id"],
            "attack_name": tpl["name"],
            "category": tpl.get("category", ""),
        })
        case_attempt = await _prepare_case_attempt(
            task, tpl, payload_text,
            quartet_mode=quartet_mode,
            ws_clients=ws_clients,
        )
        analysis = case_attempt["analysis"]
        completed, vulns, total = await _persist_and_count(task_id, task, tpl, case_attempt, analysis)
        persisted = True
        await _observe_case_response_health(task_id, case_attempt, ws_clients)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": tpl["id"],
            "attack_name": tpl["name"],
            "successful": analysis.attack_successful,
            "risk_level": analysis.risk_level,
            "completed": completed,
            "total": total,
            "vulnerabilities_found": vulns,
        })
    except Exception as exc:
        logger.warning("Base case failed %s / %s: %s", tpl["id"], payload_text[:60], exc)
    finally:
        if not persisted and not await _check_should_stop_isolated(task_id, scan_deadline):
            # Only backfill when no scan-level stop is active — an active stop
            # signal means this case was intentionally cut short and the scan
            # should end as failed/cancelled, not completed.
            await _increment_completed(task_id)
            # Tell the UI this attack is no longer in flight, even though it
            # never produced a result row. Without this the frontend's
            # runningAttacks map keeps the template_id forever and the
            # "Attacks in Flight" panel shows 6-minute zombies long after
            # the scan runner gave up on this payload.
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": tpl["id"],
                "attack_name": tpl["name"],
                "skipped": True,
            })


async def _run_multiturn_base_case(
    task_id: str,
    task,
    tpl: dict,
    ws_clients: dict,
    *,
    quartet_mode: str,
    scan_deadline: float,
) -> None:
    """Execute one multi-turn base attack case (turns are sequential) and persist.

    Same alignment semantics as ``_run_single_base_case``: successful persist
    counts via ``_persist_and_count``; single-case failures (no scan-level
    stop) are backfilled; when a scan-level stop is active we leave the
    counter alone so the scan ends as ``failed`` / ``cancelled`` honestly.
    """
    persisted = False
    try:
        payloads = tpl.get("payloads", [])
        conversation_history: list[dict] = []
        all_texts: list[str] = []
        last_response = ""
        last_session_id: str | None = None
        case_id = str(uuid.uuid4())

        for payload_obj in payloads:
            if await _check_should_stop_isolated(task_id, scan_deadline):
                return
            text = payload_obj.get("text", "")
            all_texts.append(text)
            last_response, last_session_id = await _send_to_target_with_result(
                task, text,
                case_id=case_id,
                variant_type="attack",
                conversation_history=conversation_history,
            )
            conversation_history.append({"role": "user", "content": text})
            conversation_history.append({"role": "assistant", "content": last_response})

        if not all_texts:
            return

        combined_payload = "\n---\n".join(f"[Turn {i+1}] {t}" for i, t in enumerate(all_texts))
        case_attempt = await _prepare_case_attempt(
            task, tpl, combined_payload,
            case_id=case_id,
            quartet_mode=quartet_mode,
            attack_response=last_response,
            probe_session_id=last_session_id,
            ws_clients=ws_clients,
        )
        analysis = case_attempt["analysis"]
        completed, vulns, total = await _persist_and_count(
            task_id, task, tpl, case_attempt, analysis,
            legacy_payload_text="\n".join(f"Turn {i+1}: {t}" for i, t in enumerate(all_texts)),
        )
        persisted = True
        await _observe_case_response_health(task_id, case_attempt, ws_clients)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": tpl["id"],
            "attack_name": tpl["name"],
            "successful": analysis.attack_successful,
            "risk_level": analysis.risk_level,
            "completed": completed,
            "total": total,
            "vulnerabilities_found": vulns,
        })
    except Exception as exc:
        logger.warning("Multi-turn base case failed %s: %s", tpl["id"], exc)
    finally:
        if not persisted and not await _check_should_stop_isolated(task_id, scan_deadline):
            # See _run_single_base_case: only backfill on single-case glitches;
            # scan-level stop must still surface as failed/cancelled.
            await _increment_completed(task_id)
            # Same rationale as the single-turn case — clear the UI's
            # in-flight tracker so a zombie payload doesn't pretend to
            # still be running for hours.
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": tpl["id"],
                "attack_name": tpl["name"],
                "skipped": True,
            })


_REQUIRED_PILOT_VARIANTS: tuple[str, ...] = (
    "attack",
    "clean",
    "quoted_attack",
    "benign_distractor",
)


def _pilot_suite_path_from_config(advanced_config: dict) -> str | None:
    value = advanced_config.get("pilot_suite_path")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _load_validated_pilot_suite(advanced_config: dict):
    suite_path = _pilot_suite_path_from_config(advanced_config)
    if suite_path is None:
        raise ValueError("pilot_suite_path is required for pilot suite execution")

    suite = load_suite(Path(suite_path))
    expected_hash = str(advanced_config.get("pilot_suite_hash") or "").strip()
    if expected_hash and expected_hash != suite.manifest.content_hash:
        raise ValueError("pilot suite hash does not match ScanTask advanced_config")

    expected_case_count = advanced_config.get("pilot_case_count")
    if expected_case_count is not None and int(expected_case_count) != suite.manifest.case_count:
        raise ValueError("pilot case count does not match suite manifest")

    expected_variant_count = advanced_config.get("pilot_variant_count")
    if expected_variant_count is not None and int(expected_variant_count) != suite.manifest.case_count * 4:
        raise ValueError("pilot variant count does not match suite manifest")

    for suite_case in suite.cases:
        for variant_type in _REQUIRED_PILOT_VARIANTS:
            prompt = str(getattr(suite_case.variants, variant_type) or "")
            if not prompt.strip():
                raise ValueError(
                    f"pilot suite case {suite_case.case_id} is missing {variant_type} prompt"
                )
    return suite


def _template_from_pilot_case(suite_case) -> dict:
    template_id = str(suite_case.template_id or suite_case.case_id)
    template_name = str(suite_case.template_name or f"Pilot case {suite_case.case_id}")
    return {
        "id": template_id,
        "name": template_name,
        "category": suite_case.category,
        "category_name": suite_case.category,
        "owasp_id": suite_case.owasp_id or "",
        "technique": "pilot_suite",
    }


async def _run_base_templates(
    task_id: str,
    task,
    templates: list[dict],
    ws_clients: dict,
    *,
    quartet_mode: str,
    scan_deadline: float,
    base_sem: asyncio.Semaphore,
) -> None:
    """Dispatch all base-template cases concurrently under a shared semaphore."""
    async def _guarded(coro):
        async with base_sem:
            await coro

    coros = []
    for tpl in templates:
        if tpl.get("multi_turn"):
            coros.append(_run_multiturn_base_case(
                task_id, task, tpl, ws_clients,
                quartet_mode=quartet_mode,
                scan_deadline=scan_deadline,
            ))
        else:
            for payload_obj in tpl.get("payloads", []):
                payload_text = payload_obj.get("text", "")
                if payload_text:
                    coros.append(_run_single_base_case(
                        task_id, task, tpl, payload_text, ws_clients,
                        quartet_mode=quartet_mode,
                        scan_deadline=scan_deadline,
                    ))

    if coros:
        await asyncio.gather(*[_guarded(c) for c in coros], return_exceptions=True)


async def _run_pilot_suite_cases(
    task_id: str,
    task,
    suite,
    ws_clients: dict,
    *,
    scan_deadline: float,
) -> None:
    for suite_case in suite.cases:
        if await _check_should_stop_isolated(task_id, scan_deadline):
            return

        tpl = _template_from_pilot_case(suite_case)
        persisted = False
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": tpl["id"],
            "attack_name": tpl["name"],
            "category": tpl.get("category", ""),
        })
        try:
            case_attempt = await _prepare_explicit_case_attempt(
                task,
                tpl,
                suite_case,
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id,
                task,
                tpl,
                case_attempt,
                analysis,
            )
            persisted = True
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": tpl["id"],
                "attack_name": tpl["name"],
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as exc:
            logger.warning("Pilot suite case failed %s: %s", tpl["id"], exc)
        finally:
            if not persisted and not await _check_should_stop_isolated(task_id, scan_deadline):
                await _increment_completed(task_id)
                await _broadcast(ws_clients, task_id, {
                    "type": "attack_completed",
                    "template_id": tpl["id"],
                    "attack_name": tpl["name"],
                    "skipped": True,
                })


async def run_scan(task_id: str, ws_clients: dict[str, list[WebSocket]]):
    async with async_session() as db:
        result = await db.execute(select(ScanTask).where(ScanTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error("Scan task %s not found", task_id)
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Activate per-scan provider overrides for the entire scan lifetime.
        _apply_scan_providers(task)

        adv = task.advanced_config or {}
        pilot_suite_path = _pilot_suite_path_from_config(adv)
        pilot_suite = None
        if pilot_suite_path:
            templates = []
            enable_mutations = False
        else:
            engine = AttackEngine()
            templates = engine.get_all_templates(task.attack_categories)
            enable_mutations = adv.get("enable_mutations", False)
        # quartet_mode supersedes enable_control_variants; support both for backward compat
        # Default is "adaptive": skips control variants when AI judge is already high-confidence.
        quartet_mode = adv.get("quartet_mode") or (
            "adaptive" if adv.get("enable_control_variants", True) else "off"
        )
        enable_crescendo = adv.get("enable_crescendo", False)
        enable_fitd = adv.get("enable_fitd", False)
        enable_msj = adv.get("enable_msj", False)
        enable_ice = adv.get("enable_ice", False)
        enable_tap = adv.get("enable_tap", False)
        enable_pair = adv.get("enable_pair", False)
        enable_self_explanation = adv.get("enable_self_explanation", False)
        parallel_attacks = max(1, adv.get("parallel_attacks", 3))

        if pilot_suite_path:
            enable_crescendo = False
            enable_fitd = False
            enable_msj = False
            enable_ice = False
            enable_tap = False
            enable_pair = False
            enable_self_explanation = False

        if enable_mutations:
            mutation_strategies = adv.get("mutation_strategies", []) or None
            for tpl in templates:
                original_payloads = list(tpl.get("payloads", []))
                for p in original_payloads:
                    variants = generate_variants(p.get("text", ""), mutation_strategies)
                    for v in variants[:3]:
                        tpl.setdefault("payloads", []).append({
                            "text": v["text"],
                            "language": "en",
                            "variant": f"mutation_{v['strategy']}",
                        })

        if pilot_suite_path:
            task.total_attacks = int(adv.get("pilot_case_count") or 0)
        else:
            base_attack_total = sum(_count_base_template_cases(t) for t in templates)
            # #16: 仅统计有 base_payload 的模板数量
            templates_with_payload = sum(
                1 for t in templates
                if t.get("payloads") and t["payloads"][0].get("text")
            )
            advanced_attack_total = 0
            if enable_pair:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_self_explanation:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_crescendo:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_fitd:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_msj:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_ice:
                advanced_attack_total += min(5, templates_with_payload)
            if enable_tap:
                advanced_attack_total += min(5, templates_with_payload)
            task.total_attacks = base_attack_total + advanced_attack_total
        await db.commit()

        await _broadcast(ws_clients, task_id, {
            "type": "scan_started",
            "total": task.total_attacks,
        })

        scan_deadline = asyncio.get_running_loop().time() + MAX_SCAN_DURATION_S

        stop_event = asyncio.Event()
        _scan_stop_events[task_id] = stop_event
        _scan_stop_check_ts[task_id] = 0.0
        _scan_health_trackers[task_id] = _new_scan_health_tracker(adv)

        try:
            if pilot_suite_path:
                pilot_suite = _load_validated_pilot_suite(adv)
                task.total_attacks = pilot_suite.manifest.case_count
                await db.commit()

            if task.target_type == "adapter" and not getattr(task, "_resolved_adapter_payload", None):
                setattr(
                    task,
                    "_resolved_adapter_payload",
                    await resolve_task_adapter_payload(db, task.adapter_id),
                )

            health_snapshot = await probe_target_health(task)
            async with _scan_health_trackers[task_id]["lock"]:
                _scan_health_trackers[task_id]["target_health"] = health_snapshot.get("target_health")
                _scan_health_trackers[task_id]["health_probe_passed"] = health_snapshot.get("health_probe_passed")
                _scan_health_trackers[task_id]["health_failure_reason"] = health_snapshot.get("health_failure_reason")
                _scan_health_trackers[task_id]["recent_health_signature"] = health_snapshot.get("recent_health_signature")
                _scan_health_trackers[task_id]["invalid_response_ratio"] = health_snapshot.get("invalid_response_ratio")
            _apply_scan_health_snapshot(task, health_snapshot)
            await db.commit()
            await _broadcast_scan_health(ws_clients, task_id, health_snapshot)

            if health_snapshot.get("target_health") == "unhealthy":
                # Preflight probe is diagnostic only — do NOT abort the scan here.
                # The unhealthy signal is already persisted and broadcast above so
                # the UI shows the degraded banner; each case will still run and
                # record its own response_evaluation (likely not_evaluable), which
                # is more useful to the user than a blanket abort that leaves a
                # `failed` scan with zero results.
                logger.warning(
                    "Scan %s: preflight health probe detected unhealthy target — continuing scan with health banner. reason=%s",
                    task_id,
                    health_snapshot.get("health_failure_reason"),
                )

            # Semaphores: base cases use base_sem; advanced chains share chain_sem.
            # Builtin/model-backed targets can tolerate higher cross-template fanout.
            # External/custom business endpoints are treated more conservatively and
            # respect the configured parallel_attacks directly.
            chain_sem = asyncio.Semaphore(_MAX_CONCURRENT_CHAINS)
            base_parallelism = (
                parallel_attacks
                if task.target_type in {"adapter", "custom"}
                else parallel_attacks * 2
            )
            base_sem = asyncio.Semaphore(base_parallelism)

            async def parallel_should_stop() -> bool:
                return await _check_should_stop_isolated(task_id, scan_deadline)

            if pilot_suite is not None:
                await _run_pilot_suite_cases(
                    task_id,
                    task,
                    pilot_suite,
                    ws_clients,
                    scan_deadline=scan_deadline,
                )
                gather_results = []
            else:
                # Build all coroutines: base templates + advanced engines run together.
                all_coros: list[Coroutine] = [
                    _run_base_templates(
                        task_id, task, templates, ws_clients,
                        quartet_mode=quartet_mode,
                        scan_deadline=scan_deadline,
                        base_sem=base_sem,
                    )
                ]
                if enable_pair:
                    all_coros.append(_run_advanced_pair(
                        task_id, task, templates, ws_clients,
                        adv.get("pair_max_rounds", 20),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_self_explanation:
                    all_coros.append(_run_advanced_self_explanation(
                        task_id, task, templates, ws_clients,
                        adv.get("self_explanation_rounds", 5),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_crescendo:
                    all_coros.append(_run_advanced_crescendo(
                        task_id, task, templates, ws_clients,
                        adv.get("crescendo_max_turns", 10),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_fitd:
                    all_coros.append(_run_advanced_fitd(
                        task_id, task, templates, ws_clients,
                        adv.get("fitd_num_levels", 6),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_msj:
                    all_coros.append(_run_advanced_msj(
                        task_id, task, templates, ws_clients,
                        adv.get("msj_shot_count", 32),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_ice:
                    all_coros.append(_run_advanced_ice(
                        task_id, task, templates, ws_clients,
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))
                if enable_tap:
                    all_coros.append(_run_advanced_tap(
                        task_id, task, templates, ws_clients,
                        adv.get("tap_branching_factor", 4),
                        adv.get("tap_max_depth", 10),
                        quartet_mode=quartet_mode,
                        should_stop=parallel_should_stop,
                        chain_sem=chain_sem,
                    ))

                gather_results = await asyncio.gather(*all_coros, return_exceptions=True)
            for idx, res in enumerate(gather_results):
                if isinstance(res, Exception):
                    logger.warning("Engine %d failed: %s", idx, res)

            all_results = [
                {
                    "attack_successful": r.attack_successful,
                    "risk_score": r.risk_score,
                    "verdict_status": (r.analysis_raw or {}).get("verdict_status"),
                    "target_response": r.target_response,
                }
                for r in (await db.execute(
                    select(AttackResult).where(AttackResult.scan_task_id == task_id)
                )).scalars().all()
            ]
            overall_score = compute_overall_score(all_results)

            await db.refresh(
                task,
                attribute_names=[
                    "status",
                    "completed_at",
                    "vulnerabilities_found",
                    "completed_attacks",
                    "total_attacks",
                    "target_health",
                    "health_probe_passed",
                    "health_failure_reason",
                    "recent_health_signature",
                    "invalid_response_ratio",
                ],
            )
            task.overall_score = overall_score
            final_status = task.status
            incomplete_scan = task.completed_attacks < task.total_attacks
            if task.status in ACTIVE_SCAN_STATUSES:
                final_status = "failed" if incomplete_scan else "completed"
                task.status = final_status
            if task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
            await db.commit()

            if final_status == "completed":
                await _broadcast(ws_clients, task_id, {
                    "type": "scan_completed",
                    "overall_score": overall_score,
                    "risk_level": classify_overall_risk(overall_score),
                    "total": task.total_attacks,
                    "vulnerabilities_found": task.vulnerabilities_found,
                    "target_health": task.target_health,
                    "health_probe_passed": task.health_probe_passed,
                    "health_failure_reason": task.health_failure_reason,
                    "recent_health_signature": task.recent_health_signature,
                    "invalid_response_ratio": task.invalid_response_ratio,
                })
            elif final_status == "failed":
                logger.warning(
                    "Scan %s ended early: completed %s/%s attacks",
                    task_id,
                    task.completed_attacks,
                    task.total_attacks,
                )
                await _broadcast(ws_clients, task_id, {
                    "type": "scan_failed",
                    "error": (
                        f"Scan ended early after {task.completed_attacks}/{task.total_attacks} attacks"
                    ),
                    "target_health": task.target_health,
                    "health_probe_passed": task.health_probe_passed,
                    "health_failure_reason": task.health_failure_reason,
                    "recent_health_signature": task.recent_health_signature,
                    "invalid_response_ratio": task.invalid_response_ratio,
                })

        except Exception:
            await db.rollback()
            logger.exception("Scan %s failed", task_id)
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await _broadcast(ws_clients, task_id, {"type": "scan_failed", "error": "Internal error"})

        finally:
            _scan_stop_events.pop(task_id, None)
            _scan_stop_check_ts.pop(task_id, None)
            _scan_health_trackers.pop(task_id, None)


async def _run_advanced_crescendo(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    max_turns: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    logger.info("Running Crescendo attacks for scan %s", task_id)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []

        async def send_fn(message: str, history: list[dict] | None = None) -> str:
            envelope = await _invoke_target_with_envelope(
                task, message, case_id=case_id, variant_type="attack",
                conversation_history=history,
            )
            return _record_envelope_attempt(probe_attempts, message, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"CR-{tpl['id']}",
            "attack_name": f"Crescendo: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_crescendo(objective, send_fn, max_rounds=max_turns, should_stop=should_stop)
            if should_stop and await should_stop():
                return False
            attack_payload = "\n---\n".join(f"[Turn {t.turn_number}] Q: {t.question}" for t in result.turns)
            resolved_response = result.final_response or _last_non_empty(result.turns, "response")
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, attack_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"Crescendo Multi-Turn {tpl.get('category_name', '')}",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=attack_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"CR-{tpl['id']}",
                record_attack_name=f"Crescendo: {tpl['name']}",
                record_technique=f"crescendo_{tpl.get('technique', '')}",
                legacy_payload_text="\n".join(f"Turn {turn.turn_number}: {turn.question}" for turn in result.turns),
                legacy_analysis_extra={
                    "crescendo_turns": result.total_turns, "crescendo_success": result.success,
                    "crescendo_strategy_log": result.strategy_log,
                    "crescendo_turns_detail": [
                        {"turn_number": t.turn_number, "question": t.question, "response": t.response,
                         "refused": t.refused, "judge_score": t.judge_score, "judge_success": t.judge_success}
                        for t in result.turns
                    ],
                },
            )
        except Exception:
            raise  # propagate to _gather_engine_tasks for retry
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed", "template_id": f"CR-{tpl['id']}",
                "attack_name": f"Crescendo: {tpl['name']}", "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level, "completed": completed, "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for Crescendo %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"CR-{tpl['id']}",
            "attack_name": f"Crescendo: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "Crescendo",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_tap(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    branching_factor: int,
    max_depth: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    logger.info("Running TAP attacks for scan %s", task_id)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(prompt: str) -> str:
            envelope = await _invoke_target_with_envelope(
                task, prompt, case_id=case_id, variant_type="attack",
            )
            return _record_envelope_attempt(probe_attempts, prompt, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started", "template_id": f"TAP-{tpl['id']}",
            "attack_name": f"TAP: {tpl['name']}", "category": tpl.get("category", ""),
        })
        try:
            result = await run_tap(
                base_payload, objective, send_fn,
                branching_factor=branching_factor, max_depth=max_depth, should_stop=should_stop,
            )
            if should_stop and await should_stop():
                return False
            attack_payload = result.best_prompt or base_payload
            resolved_response = result.best_response or _last_non_empty(result.all_attempts, "response")
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, attack_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"TAP Auto-Generated {tpl.get('category_name', '')}",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=attack_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"TAP-{tpl['id']}",
                record_attack_name=f"TAP: {tpl['name']}",
                record_technique=f"tap_{tpl.get('technique', '')}",
                legacy_analysis_extra={
                    "tap_queries": result.total_queries,
                    "tap_variants": result.variants_generated,
                    "tap_best_score": result.best_score,
                    "tap_depth_reached": result.depth_reached,
                    "tap_stop_reason": result.stop_reason,
                    "tap_all_attempts": result.all_attempts,
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"TAP-{tpl['id']}",
                "attack_name": f"TAP: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for TAP %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"TAP-{tpl['id']}",
            "attack_name": f"TAP: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "TAP",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_pair(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    max_rounds: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    logger.info("Running PAIR attacks for scan %s", task_id)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(prompt: str) -> str:
            envelope = await _invoke_target_with_envelope(
                task, prompt, case_id=case_id, variant_type="attack",
            )
            return _record_envelope_attempt(probe_attempts, prompt, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"PAIR-{tpl['id']}",
            "attack_name": f"PAIR: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_pair(
                base_payload, objective, send_fn, max_rounds=max_rounds, should_stop=should_stop,
            )
            if should_stop and await should_stop():
                return False
            attack_payload = result.best_prompt or base_payload
            resolved_response = result.best_response or _last_non_empty(result.attempts, "response")
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, attack_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"PAIR Iterative Refinement {tpl.get('category_name', '')}",
                extra_context=f"PAIR best score: {result.best_score}/10 across {len(result.attempts)} rounds.",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=attack_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"PAIR-{tpl['id']}",
                record_attack_name=f"PAIR: {tpl['name']}",
                record_technique=f"pair_{tpl.get('technique', '')}",
                legacy_analysis_extra={
                    "pair_best_score": result.best_score,
                    "pair_total_queries": result.total_queries,
                    "pair_attempts": [
                        {
                            "round_number": a.round_number,
                            "prompt": a.prompt,
                            "response": a.response,
                            "score": a.score,
                            "reasoning": a.reasoning,
                            "improvement": a.improvement,
                            "strategy": a.strategy,
                        }
                        for a in result.attempts
                    ],
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"PAIR-{tpl['id']}",
                "attack_name": f"PAIR: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for PAIR %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"PAIR-{tpl['id']}",
            "attack_name": f"PAIR: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "PAIR",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_self_explanation(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    max_rounds: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    logger.info("Running IRIS-inspired self-explanation attacks for scan %s", task_id)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(prompt: str) -> str:
            envelope = await _invoke_target_with_envelope(
                task, prompt, case_id=case_id, variant_type="attack",
            )
            return _record_envelope_attempt(probe_attempts, prompt, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"IRIS-{tpl['id']}",
            "attack_name": f"Self-Explanation: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_iris(
                base_payload, objective, send_fn, max_rounds=max_rounds, should_stop=should_stop,
            )
            if should_stop and await should_stop():
                return False
            attack_payload = result.best_prompt or base_payload
            resolved_response = result.best_response or _last_non_empty(result.rounds, "response")
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, attack_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"IRIS Self-Explanation {tpl.get('category_name', '')}",
                extra_context=f"IRIS best score: {result.best_score}/10 across {len(result.rounds)} rounds.",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=attack_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"IRIS-{tpl['id']}",
                record_attack_name=f"Self-Explanation: {tpl['name']}",
                record_technique=f"self_explanation_{tpl.get('technique', '')}",
                legacy_analysis_extra={
                    "iris_best_score": result.best_score,
                    "iris_total_queries": result.total_queries,
                    "iris_rounds": [
                        {
                            "round_number": r.round_number,
                            "prompt": r.prompt,
                            "response": r.response,
                            "score": r.score,
                            "reasoning": r.reasoning,
                            "self_explanation": r.self_explanation,
                            "strategy": r.strategy,
                        }
                        for r in result.rounds
                    ],
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"IRIS-{tpl['id']}",
                "attack_name": f"Self-Explanation: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for Self-Explanation %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"IRIS-{tpl['id']}",
            "attack_name": f"Self-Explanation: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "Self-Explanation",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_fitd(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    num_levels: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    """Run FITD (Foot-In-The-Door) escalation attacks against up to 5 templates."""
    logger.info("Running FITD attacks for scan %s (%d levels)", task_id, num_levels)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(message: str, history: list[dict] | None = None) -> str:
            envelope = await _invoke_target_with_envelope(
                task, message, case_id=case_id, variant_type="attack",
                conversation_history=history,
            )
            return _record_envelope_attempt(probe_attempts, message, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"FITD-{tpl['id']}",
            "attack_name": f"FITD: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_fitd(objective, send_fn, num_levels=num_levels, should_stop=should_stop)
            if should_stop and await should_stop():
                return False
            ladder_summary = "\n".join(f"[L{lv.level}] {lv.prompt[:120]}" for lv in result.levels) or base_payload
            attack_payload = result.best_prompt or base_payload
            resolved_response = result.best_response or _last_non_empty(result.levels, "response")
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, attack_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"FITD Foot-In-The-Door {tpl.get('category_name', '')}",
                extra_context=(
                    f"FITD: {len(result.levels)}-level escalation, "
                    f"best_score={result.best_score:.2f}, "
                    f"queries={result.total_queries}, "
                    f"stop_reason={result.stop_reason}."
                ),
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=attack_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"FITD-{tpl['id']}",
                record_attack_name=f"FITD: {tpl['name']}",
                record_technique=f"fitd_{tpl.get('technique', '')}",
                legacy_payload_text=ladder_summary,
                legacy_analysis_extra={
                    "fitd_success": result.success,
                    "fitd_best_score": result.best_score,
                    "fitd_total_queries": result.total_queries,
                    "fitd_num_levels": len(result.levels),
                    "fitd_stop_reason": result.stop_reason,
                    "fitd_escalation_ladder": result.escalation_ladder,
                    "fitd_levels": [
                        {
                            "level": lv.level,
                            "prompt": lv.prompt,
                            "was_refused": lv.was_refused,
                            "was_realigned": lv.was_realigned,
                            "midpoint_used": lv.midpoint_used,
                        }
                        for lv in result.levels
                    ],
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"FITD-{tpl['id']}",
                "attack_name": f"FITD: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for FITD %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"FITD-{tpl['id']}",
            "attack_name": f"FITD: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "FITD",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_msj(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    n_shots: int,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    """Run Many-Shot Jailbreaking attacks against up to 5 templates."""
    logger.info("Running MSJ attacks for scan %s (%d shots)", task_id, n_shots)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(message: str, history: list[dict] | None = None) -> str:
            envelope = await _invoke_target_with_envelope(
                task, message, case_id=case_id, variant_type="attack",
                conversation_history=history,
            )
            return _record_envelope_attempt(probe_attempts, message, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"MSJ-{tpl['id']}",
            "attack_name": f"MSJ: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_msj(
                base_payload, objective, send_fn, n_shots=n_shots, should_stop=should_stop,
            )
            if should_stop and await should_stop():
                return False
            resolved_response = result.response or ""
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, base_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"MSJ Many-Shot {tpl.get('category_name', '')}",
                extra_context=f"MSJ: {result.n_shots} shots, prompt_length={result.msj_prompt_length} chars.",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=base_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"MSJ-{tpl['id']}",
                record_attack_name=f"MSJ: {tpl['name']}",
                record_technique=f"msj_{tpl.get('technique', '')}",
                legacy_analysis_extra={
                    "msj_n_shots": result.n_shots,
                    "msj_prompt_length": result.msj_prompt_length,
                    "msj_success": result.success,
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"MSJ-{tpl['id']}",
                "attack_name": f"MSJ: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for MSJ %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"MSJ-{tpl['id']}",
            "attack_name": f"MSJ: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "MSJ",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )


async def _run_advanced_ice(
    task_id: str,
    task: ScanTask,
    templates: list[dict],
    ws_clients: dict,
    quartet_mode: str = "full",
    should_stop: Callable[[], Awaitable[bool]] | None = None,
    chain_sem: asyncio.Semaphore | None = None,
):
    """Run ICE (Intent Concealment & Diversion) attacks against up to 5 templates."""
    logger.info("Running ICE attacks for scan %s", task_id)

    async def _process_tpl(tpl: dict) -> bool:
        if should_stop and await should_stop():
            return False
        case_id = str(uuid.uuid4())
        probe_attempts: list[dict[str, str | None]] = []
        base_payload = tpl.get("payloads", [{}])[0].get("text", "")
        if not base_payload:
            return False

        async def send_fn(message: str, history: list[dict] | None = None) -> str:
            envelope = await _invoke_target_with_envelope(
                task, message, case_id=case_id, variant_type="attack",
                conversation_history=history,
            )
            return _record_envelope_attempt(probe_attempts, message, envelope)

        objective = _build_attack_objective(tpl)
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": f"ICE-{tpl['id']}",
            "attack_name": f"ICE: {tpl['name']}",
            "category": tpl.get("category", ""),
        })
        try:
            result = await run_ice(base_payload, objective, send_fn, should_stop=should_stop)
            if should_stop and await should_stop():
                return False
            resolved_response = result.response or ""
            attack_envelope = _resolve_envelope_for_response(probe_attempts, resolved_response)
            case_attempt = await _prepare_case_attempt(
                task, tpl, base_payload, case_id=case_id, quartet_mode=quartet_mode,
                attack_response=resolved_response,
                attack_response_error=_envelope_response_error(attack_envelope),
                attack_transport_meta=_envelope_to_variant_transport_meta(attack_envelope),
                attack_session_id=attack_envelope.session_id if attack_envelope else None,
                attack_type=f"ICE Intent-Concealment {tpl.get('category_name', '')}",
                extra_context=f"ICE: {result.n_fragments} fragments, single-query reasoning mask.",
                probe_session_id=_matched_probe_session_id(
                    probe_attempts, attack_payload=base_payload, target_response=resolved_response,
                ),
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id, task, tpl, case_attempt, analysis,
                record_template_id=f"ICE-{tpl['id']}",
                record_attack_name=f"ICE: {tpl['name']}",
                record_technique=f"ice_{tpl.get('technique', '')}",
                legacy_analysis_extra={
                    "ice_n_fragments": result.n_fragments,
                    "ice_success": result.success,
                    "ice_prompt_length": len(result.ice_prompt),
                },
            )
        except Exception:
            raise
        try:
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": f"ICE-{tpl['id']}",
                "attack_name": f"ICE: {tpl['name']}",
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as e:
            logger.debug("Post-persist notification failed for ICE %s: %s", tpl.get("id"), e)
        return True

    async def _on_skip(tpl: dict) -> None:
        await _broadcast(ws_clients, task_id, {
            "type": "attack_completed",
            "template_id": f"ICE-{tpl['id']}",
            "attack_name": f"ICE: {tpl['name']}",
            "skipped": True,
        })

    await _gather_engine_tasks(
        task_id, _process_tpl, templates, "ICE",
        sem=chain_sem, should_stop=should_stop, on_skip=_on_skip,
    )
