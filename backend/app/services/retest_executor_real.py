"""Real (in-process) RetestExecutor — wires retest actions to the adapter +
collector modules so the async retest loop climbs evidence levels against a
live target/probe.

Injected into ``retest_loop.run_retest_loop_async`` (P2). Each method executes
one evidence-gathering action against the same case/target and returns a plain,
serializable :class:`EvidenceDelta`. It never sets ``contradiction`` for signals
the arbiter can already derive from merged result fields (e.g. probe-fail after a
text claim, or a quoted-control success); it only flags contradictions the
arbiter cannot see from the attack result alone.

Actions: ``run_quartet``, ``run_probe`` (P2) and ``run_canary`` (P2b) — the last
re-sends the eliciting prompt and reports which channel the configured canary
reached, letting the arbiter's ``trace_canary`` derive the evidence level.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from app.services.ai_analyzer import AnalyzerUsage
from app.services.retest_loop import EvidenceDelta
from app.services.retest_policy import RetestAction
from app.services.probe_executor import execute_probe
from app.services.canary_utils import collect_canary_tokens, find_canary_matches
from app.services.control_variants import canary_tokens_in_tool_calls
from app.services.case_executor import (
    _resolved_case_adapter_payload,
    _resolve_probe_status,
    analyze_case_variants,
    execute_case_variants,
)

# Control-comparison outcomes where a control variant tracked the attack
# behaviour closely enough that the original "success" is a false-positive
# signal the arbiter cannot see from the attack result alone.
_CONTRADICTION_ASSESSMENTS = {"discussion_supported"}


def _optional_sum_int(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right


def _optional_sum_float(
    left: float | None,
    right: float | None,
) -> float | None:
    if left is None or right is None:
        return None
    return left + right


def _variant_actual_cost(
    variant: Mapping[str, Any],
) -> tuple[int | None, float | None]:
    metadata = variant.get("transport_meta")
    if not isinstance(metadata, Mapping):
        return None, None
    usage = metadata.get("usage")
    usage_mapping = usage if isinstance(usage, Mapping) else metadata
    raw_tokens = usage_mapping.get("total_tokens")
    raw_cost = usage_mapping.get("monetary_cost_usd")
    if raw_cost is None:
        raw_cost = usage_mapping.get("cost_usd")
    token_count = int(raw_tokens) if isinstance(raw_tokens, int) else None
    monetary_cost = float(raw_cost) if isinstance(raw_cost, (int, float)) else None
    return token_count, monetary_cost


def _target_actual_cost(
    task: Any,
    variants: list[Mapping[str, Any]],
) -> tuple[int | None, float | None]:
    if getattr(task, "target_type", None) == "builtin_vulnerable":
        return 0, 0.0
    costs = [_variant_actual_cost(variant) for variant in variants]
    if not costs:
        return 0, 0.0
    if any(tokens is None for tokens, _ in costs):
        token_count = None
    else:
        token_count = sum(tokens for tokens, _ in costs if tokens is not None)
    if any(cost is None for _, cost in costs):
        monetary_cost = None
    else:
        monetary_cost = sum(cost for _, cost in costs if cost is not None)
    return token_count, monetary_cost


class RealRetestExecutor:
    def __init__(
        self,
        task: Any,
        template: Mapping[str, Any] | None = None,
        *,
        judge_provider_id: str | None = None,
        judge_model_version: str | None = None,
    ) -> None:
        if (judge_provider_id is None) != (judge_model_version is None):
            raise ValueError(
                "judge_provider_id and judge_model_version must be provided together"
            )
        self.task = task
        self.template = dict(template or {})
        self.judge_provider_id = judge_provider_id
        self.judge_model_version = judge_model_version

    def executable_action_types(
        self,
        actions: tuple[RetestAction, ...],
        result: Mapping[str, Any],
    ) -> tuple[str, ...]:
        executable: list[str] = []
        for action in actions:
            if action.action_type == "run_quartet":
                executable.append(action.action_type)
            elif action.action_type == "run_canary_retest":
                target_config = getattr(self.task, "target_config", None) or {}
                if collect_canary_tokens(target_config):
                    executable.append(action.action_type)
            elif (
                action.action_type == "run_probe"
                and self._resolved_probe_payload() is not None
            ):
                executable.append(action.action_type)
        return tuple(executable)

    def _resolved_probe_payload(self) -> dict[str, Any] | None:
        adapter_payload = _resolved_case_adapter_payload(self.task)
        if (
            adapter_payload is None
            and getattr(self.task, "target_type", None) == "builtin_vulnerable"
        ):
            target_config = getattr(self.task, "target_config", None) or {}
            builtin_probe_config = target_config.get("builtin_probe_config")
            if builtin_probe_config:
                adapter_payload = {
                    "enabled": True,
                    "mode": "builtin_vulnerable",
                    "probe_config": builtin_probe_config,
                }
        if not isinstance(adapter_payload, dict) or not adapter_payload.get(
            "probe_config"
        ):
            return None
        return adapter_payload

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
            attack_response=attack_response
            if isinstance(attack_response, str)
            else None,
        )
        analyzer_kwargs: dict[str, str] = {}
        if self.judge_provider_id is not None:
            analyzer_kwargs = {
                "judge_provider_id": self.judge_provider_id,
                "judge_model_version": self.judge_model_version or "",
            }
        analyzer_usage = AnalyzerUsage()
        analyzed = await analyze_case_variants(
            self.task,
            self.template,
            case_variants,
            analyzer_usage=analyzer_usage,
            **analyzer_kwargs,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        control_summary = analyzed.get("control_summary") or {}
        control_assessment = control_summary.get("control_assessment")
        case_summary = analyzed.get("case_summary") or {}

        controls = [
            cv for cv in case_variants if str(cv.get("variant_type")) != "attack"
        ]
        extra_queries = len(controls)
        target_tokens, target_cost = _target_actual_cost(self.task, controls)
        if analyzer_usage.judge_queries == 0:
            judge_tokens: int | None = 0
            judge_cost: float | None = 0.0
        elif self.judge_provider_id == "builtin":
            judge_tokens = 0
            judge_cost = 0.0
        else:
            judge_tokens = None
            judge_cost = None
        extra_cost_ms = (
            sum(float(cv.get("latency_ms") or 0.0) for cv in controls) or elapsed_ms
        )

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
            target_retest_queries=extra_queries,
            judge_queries=analyzer_usage.judge_queries,
            actual_token_count=_optional_sum_int(target_tokens, judge_tokens),
            actual_monetary_cost_usd=_optional_sum_float(
                target_cost,
                judge_cost,
            ),
            summary=f"quartet -> {control_assessment}",
        )

    async def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta:
        target_config = getattr(self.task, "target_config", None) or {}
        tokens = collect_canary_tokens(target_config)
        if not tokens:
            return EvidenceDelta(
                action_type="run_canary", summary="no canary tokens configured"
            )

        attack_payload = str(
            result.get("payload_text")
            or result.get("attack_payload")
            or result.get("request_text")
            or ""
        )
        case_id = str(result.get("case_id") or "") or None

        started = time.perf_counter()
        variants = await execute_case_variants(
            self.task,
            self.template,
            attack_payload,
            case_id=case_id,
            quartet_mode="off",
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        attack = variants[0] if variants else {}
        actual_tokens, actual_cost = _target_actual_cost(
            self.task,
            [attack] if attack else [],
        )
        response_text = str(attack.get("response_text") or "")
        tool_calls = attack.get("tool_calls") or []

        matched = list(
            dict.fromkeys(
                find_canary_matches(response_text, tokens)
                + canary_tokens_in_tool_calls(tokens, tool_calls)
            )
        )
        if not matched:
            return EvidenceDelta(
                action_type="run_canary",
                extra_queries=1,
                extra_cost_ms=float(attack.get("latency_ms") or 0.0) or elapsed_ms,
                target_retest_queries=1,
                actual_token_count=actual_tokens,
                actual_monetary_cost_usd=actual_cost,
                summary="canary not observed",
            )

        hits = list(result.get("rule_hits") or [])
        hits.append(
            {
                "rule": "canary_token_match",
                "evidence": f"Matched canary tokens: {', '.join(matched[:5])}",
                "matched_tokens": matched,
            }
        )
        # Provenance (quoted E1 / leaked E3 / tool_call E4 / business E5) is
        # derived by the arbiter's trace_canary from these fields — a demotion
        # to E1 is not a contradiction, so this action never sets one.
        return EvidenceDelta(
            action_type="run_canary",
            evidence_updates={"rule_hits": hits, "tool_calls": list(tool_calls)},
            extra_queries=1,
            extra_cost_ms=float(attack.get("latency_ms") or 0.0) or elapsed_ms,
            target_retest_queries=1,
            actual_token_count=actual_tokens,
            actual_monetary_cost_usd=actual_cost,
            summary=f"canary observed ({len(matched)} token(s))",
        )

    async def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta:
        adapter_payload = self._resolved_probe_payload()
        if adapter_payload is None:
            return EvidenceDelta(
                action_type="run_probe", summary="probe_config unavailable"
            )
        probe_config = adapter_payload["probe_config"]

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
                probe_steps=1,
                actual_token_count=(
                    0
                    if getattr(self.task, "target_type", None) == "builtin_vulnerable"
                    else None
                ),
                actual_monetary_cost_usd=(
                    0.0
                    if getattr(self.task, "target_type", None) == "builtin_vulnerable"
                    else None
                ),
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
            probe_steps=max(step_count, 1),
            actual_token_count=(
                0
                if getattr(self.task, "target_type", None) == "builtin_vulnerable"
                else None
            ),
            actual_monetary_cost_usd=(
                0.0
                if getattr(self.task, "target_type", None) == "builtin_vulnerable"
                else None
            ),
            summary=f"probe -> {status}",
        )
