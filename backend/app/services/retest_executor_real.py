"""Real (in-process) RetestExecutor — wires retest actions to the adapter +
collector modules so the async retest loop climbs evidence levels against a
live target/probe.

Injected into ``retest_loop.run_retest_loop_async`` (P2). Each method executes
one evidence-gathering action against the same case/target and returns a plain,
serializable :class:`EvidenceDelta`. It never sets ``contradiction`` for signals
the arbiter can already derive from merged result fields (e.g. probe-fail after a
text claim, or a quoted-control success); it only flags contradictions the
arbiter cannot see from the attack result alone.

Scope (P2): ``run_quartet`` and ``run_probe``. ``run_canary`` is deferred to P2b
(it needs a real fresh-canary re-send path) and returns a no-op delta for now.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from app.services.retest_loop import EvidenceDelta
from app.services.probe_executor import execute_probe
from app.services.case_executor import (
    _resolved_case_adapter_payload,
    _resolve_probe_status,
    analyze_case_variants,
    execute_case_variants,
)

# Control-comparison outcomes where a control variant tracked the attack
# behaviour closely enough that the original "success" is a false-positive
# signal the arbiter cannot see from the attack result alone.
_CONTRADICTION_ASSESSMENTS = {"discussion_supported", "controls_inconclusive"}


class RealRetestExecutor:
    def __init__(self, task: Any, template: Mapping[str, Any] | None = None) -> None:
        self.task = task
        self.template = dict(template or {})

    async def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta:
        attack_payload = str(
            result.get("payload_text")
            or result.get("attack_payload")
            or result.get("request_text")
            or ""
        )
        case_id = str(result.get("case_id") or "") or None
        attack_response = result.get("target_response") or result.get("response_text")

        started = time.perf_counter()
        case_variants = await execute_case_variants(
            self.task,
            self.template,
            attack_payload,
            case_id=case_id,
            quartet_mode="full",
            attack_response=attack_response if isinstance(attack_response, str) else None,
        )
        analyzed = await analyze_case_variants(self.task, self.template, case_variants)
        elapsed_ms = (time.perf_counter() - started) * 1000

        control_summary = analyzed.get("control_summary") or {}
        control_assessment = control_summary.get("control_assessment")
        case_summary = analyzed.get("case_summary") or {}

        controls = [cv for cv in case_variants if str(cv.get("variant_type")) != "attack"]
        extra_queries = len(controls)
        extra_cost_ms = sum(
            float(cv.get("latency_ms") or 0.0) for cv in controls
        ) or elapsed_ms

        contradiction = control_assessment in _CONTRADICTION_ASSESSMENTS
        evidence_updates: dict[str, Any] = {}
        if not contradiction:
            if case_summary.get("tool_observed"):
                evidence_updates["tool_observed"] = True
                if case_summary.get("tool_calls"):
                    evidence_updates["tool_calls"] = case_summary.get("tool_calls")
            elif control_assessment == "attack_delta_supported":
                hits = list(result.get("rule_hits") or [])
                hits.append(
                    {
                        "rule": "quartet_attack_delta",
                        "evidence": control_summary.get("control_summary")
                        or "attack-only delta vs. controls",
                    }
                )
                evidence_updates["rule_hits"] = hits

        return EvidenceDelta(
            action_type="run_quartet",
            evidence_updates=evidence_updates,
            contradiction=contradiction,
            extra_queries=extra_queries,
            extra_cost_ms=extra_cost_ms,
            summary=f"quartet -> {control_assessment}",
        )

    async def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta:
        # Deferred to P2b: requires a real fresh-canary re-send path.
        return EvidenceDelta(action_type="run_canary", summary="canary retest not available (P2b)")

    async def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta:
        adapter_payload = _resolved_case_adapter_payload(self.task)
        probe_config = (
            adapter_payload.get("probe_config") if isinstance(adapter_payload, dict) else None
        )
        if not adapter_payload or not probe_config:
            return EvidenceDelta(action_type="run_probe", summary="probe_config unavailable")

        session_id = result.get("probe_session_id") or result.get("session_id")
        started = time.perf_counter()
        try:
            probe_response = await execute_probe(
                adapter_payload,
                probe_config=probe_config,
                runtime_vars=getattr(self.task, "runtime_vars", None) or {},
                session_id=session_id if isinstance(session_id, str) else None,
                scan_id=getattr(self.task, "id", None),
                case_id=str(result.get("case_id") or "") or None,
                variant_type="attack",
            )
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return EvidenceDelta(
                action_type="run_probe",
                evidence_updates={"business_verification_status": "probe_inconclusive"},
                extra_queries=1,
                extra_cost_ms=elapsed_ms,
                summary="probe raised -> inconclusive",
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        status = _resolve_probe_status(probe_response)
        step_count = len(getattr(probe_response, "step_results", None) or [])
        return EvidenceDelta(
            action_type="run_probe",
            evidence_updates={"business_verification_status": status},
            extra_queries=max(step_count, 1),
            extra_cost_ms=elapsed_ms,
            summary=f"probe -> {status}",
        )
