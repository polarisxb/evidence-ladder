# backend/app/services/retest_loop.py
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from app.services.evidence_arbiter import (
    EvidenceAssessment,
    arbitrate_evidence,
)
from app.services.retest_policy import (
    RetestAction,
    RetestConfig,
    plan_retests,
)


@dataclass(frozen=True)
class EvidenceDelta:
    """One retest action's evidence contribution.

    ``evidence_updates`` are merged into the result mapping and re-arbitrated.
    ``contradiction`` is an explicit signal (e.g., the quoted control also
    "succeeded") that the arbiter cannot derive from the attack result alone.
    """

    action_type: str
    evidence_updates: Mapping[str, Any] = field(default_factory=dict)
    contradiction: bool = False
    extra_queries: int = 0
    extra_cost_ms: float = 0.0
    summary: str = ""


def merge_evidence(result: Mapping[str, Any], delta: EvidenceDelta) -> dict[str, Any]:
    """Return a new result with ``delta.evidence_updates`` merged in (pure).

    Nested mappings are shallow-merged one level; other keys are replaced.
    """
    merged = copy.deepcopy(dict(result))
    for key, value in delta.evidence_updates.items():
        existing = merged.get(key)
        if isinstance(value, Mapping) and isinstance(existing, Mapping):
            nested = dict(existing)
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


TerminalVerdict = Literal["confirmed", "overturned", "manual_review", "not_evaluable"]
ConvergedReason = Literal[
    "strong_evidence", "overturned", "stall", "max_rounds", "not_evaluable", "no_action"
]

_CONTRADICTION_CONFLICTS = {"text_claim_probe_failed", "quoted_attack_success"}


@dataclass(frozen=True)
class RoundDecision:
    terminal: bool
    verdict: TerminalVerdict | None = None
    reason: ConvergedReason | None = None


def is_contradicted(assessment: EvidenceAssessment, round_contradiction: bool) -> bool:
    return round_contradiction or any(
        c in _CONTRADICTION_CONFLICTS for c in assessment.conflict_types
    )


def classify_round(
    *,
    assessment: EvidenceAssessment,
    contradicted: bool,
    level_before: str | None,
    rounds_used: int,
    config: RetestConfig,
) -> RoundDecision:
    if not assessment.is_evaluable:
        return RoundDecision(True, "not_evaluable", "not_evaluable")
    if assessment.is_strong_evidence:
        return RoundDecision(True, "confirmed", "strong_evidence")
    if contradicted:
        return RoundDecision(True, "overturned", "overturned")
    if rounds_used >= config.max_retest_rounds:
        return RoundDecision(True, "manual_review", "max_rounds")
    if rounds_used > 0 and assessment.evidence_level == level_before:
        return RoundDecision(True, "manual_review", "stall")
    return RoundDecision(False)


@dataclass(frozen=True)
class RetestRound:
    round_index: int
    trigger_conflicts: tuple[str, ...]
    actions: tuple[dict[str, str], ...]
    evidence_before: str | None
    evidence_after: str | None
    delta_summary: str
    extra_queries: int = 0
    extra_cost_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "trigger_conflicts": list(self.trigger_conflicts),
            "actions": [dict(a) for a in self.actions],
            "evidence_before": self.evidence_before,
            "evidence_after": self.evidence_after,
            "delta_summary": self.delta_summary,
            "extra_queries": self.extra_queries,
            "extra_cost_ms": self.extra_cost_ms,
        }


@dataclass
class RetestLineage:
    case_id: str
    initial_evidence_level: str | None
    initial_conflict_types: tuple[str, ...]
    rounds: list[RetestRound] = field(default_factory=list)
    final_verdict: TerminalVerdict | None = None
    final_evidence_level: str | None = None
    converged_reason: ConvergedReason | None = None

    @property
    def total_extra_queries(self) -> int:
        return sum(r.extra_queries for r in self.rounds)

    @property
    def total_extra_cost_ms(self) -> float:
        return sum(r.extra_cost_ms for r in self.rounds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "initial_evidence_level": self.initial_evidence_level,
            "initial_conflict_types": list(self.initial_conflict_types),
            "rounds": [r.to_dict() for r in self.rounds],
            "final_verdict": self.final_verdict,
            "final_evidence_level": self.final_evidence_level,
            "converged_reason": self.converged_reason,
            "total_extra_queries": self.total_extra_queries,
            "total_extra_cost_ms": self.total_extra_cost_ms,
        }


_ACTION_METHOD = {
    "run_quartet": "run_quartet",
    "run_canary_retest": "run_canary",
    "run_probe": "run_probe",
}


class RetestExecutor(Protocol):
    def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta: ...
    def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta: ...
    def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta: ...


def dispatch_action(executor: RetestExecutor, action: RetestAction,
                    result: Mapping[str, Any]) -> EvidenceDelta:
    method_name = _ACTION_METHOD.get(action.action_type)
    if method_name is None:
        raise ValueError(f"unknown retest action_type: {action.action_type!r}")
    return getattr(executor, method_name)(result)


def run_retest_loop(
    result: Mapping[str, Any],
    executor: RetestExecutor,
    config: RetestConfig | None = None,
) -> RetestLineage:
    config = config or RetestConfig()
    current: dict[str, Any] = dict(result)
    assessment = arbitrate_evidence(current)
    lineage = RetestLineage(
        case_id=str(current.get("case_id") or ""),
        initial_evidence_level=assessment.evidence_level,
        initial_conflict_types=assessment.conflict_types,
    )

    rounds_used = 0
    while True:
        decision = classify_round(
            assessment=assessment,
            contradicted=is_contradicted(assessment, False),
            level_before=assessment.evidence_level,
            rounds_used=rounds_used,
            config=config,
        )
        if decision.terminal:
            return _finalize(lineage, decision, assessment)

        round_cfg = replace(config, current_retest_round=rounds_used)
        actions = plan_retests(current, round_cfg)
        if not actions:
            return _finalize(
                lineage, RoundDecision(True, "manual_review", "no_action"), assessment
            )

        level_before = assessment.evidence_level
        deltas = [dispatch_action(executor, a, current) for a in actions]
        round_contradiction = any(d.contradiction for d in deltas)
        for d in deltas:
            current = merge_evidence(current, d)
        assessment = arbitrate_evidence(current)
        rounds_used += 1

        lineage.rounds.append(
            RetestRound(
                round_index=rounds_used,
                trigger_conflicts=tuple(a.reason for a in actions),
                actions=tuple(a.to_dict() for a in actions),
                evidence_before=level_before,
                evidence_after=assessment.evidence_level,
                delta_summary="; ".join(d.summary for d in deltas if d.summary),
                extra_queries=sum(d.extra_queries for d in deltas),
                extra_cost_ms=sum(d.extra_cost_ms for d in deltas),
            )
        )

        decision = classify_round(
            assessment=assessment,
            contradicted=is_contradicted(assessment, round_contradiction),
            level_before=level_before,
            rounds_used=rounds_used,
            config=config,
        )
        if decision.terminal:
            return _finalize(lineage, decision, assessment)


def _finalize(
    lineage: RetestLineage, decision: RoundDecision, assessment: EvidenceAssessment
) -> RetestLineage:
    lineage.final_verdict = decision.verdict
    lineage.final_evidence_level = assessment.evidence_level
    lineage.converged_reason = decision.reason
    return lineage


# ── Async twin (P2) ──────────────────────────────────────────────────────────
# The sync loop above stays pure and DB/IO-free (Fake executor only). Real
# executors (quartet/probe) do async target/probe IO and are driven from
# scan_runner's running event loop, so they need an async orchestrator. It
# reuses every pure helper (classify_round / merge_evidence / _finalize) and
# only mirrors the ``while`` loop with ``await``ed dispatch.


class AsyncRetestExecutor(Protocol):
    async def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta: ...
    async def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta: ...
    async def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta: ...


async def dispatch_action_async(
    executor: AsyncRetestExecutor, action: RetestAction, result: Mapping[str, Any]
) -> EvidenceDelta:
    method_name = _ACTION_METHOD.get(action.action_type)
    if method_name is None:
        raise ValueError(f"unknown retest action_type: {action.action_type!r}")
    return await getattr(executor, method_name)(result)


async def run_retest_loop_async(
    result: Mapping[str, Any],
    executor: AsyncRetestExecutor,
    config: RetestConfig | None = None,
) -> RetestLineage:
    config = config or RetestConfig()
    current: dict[str, Any] = dict(result)
    assessment = arbitrate_evidence(current)
    lineage = RetestLineage(
        case_id=str(current.get("case_id") or ""),
        initial_evidence_level=assessment.evidence_level,
        initial_conflict_types=assessment.conflict_types,
    )

    rounds_used = 0
    while True:
        decision = classify_round(
            assessment=assessment,
            contradicted=is_contradicted(assessment, False),
            level_before=assessment.evidence_level,
            rounds_used=rounds_used,
            config=config,
        )
        if decision.terminal:
            return _finalize(lineage, decision, assessment)

        round_cfg = replace(config, current_retest_round=rounds_used)
        actions = plan_retests(current, round_cfg)
        if not actions:
            return _finalize(
                lineage, RoundDecision(True, "manual_review", "no_action"), assessment
            )

        level_before = assessment.evidence_level
        deltas = [await dispatch_action_async(executor, a, current) for a in actions]
        round_contradiction = any(d.contradiction for d in deltas)
        for d in deltas:
            current = merge_evidence(current, d)
        assessment = arbitrate_evidence(current)
        rounds_used += 1

        lineage.rounds.append(
            RetestRound(
                round_index=rounds_used,
                trigger_conflicts=tuple(a.reason for a in actions),
                actions=tuple(a.to_dict() for a in actions),
                evidence_before=level_before,
                evidence_after=assessment.evidence_level,
                delta_summary="; ".join(d.summary for d in deltas if d.summary),
                extra_queries=sum(d.extra_queries for d in deltas),
                extra_cost_ms=sum(d.extra_cost_ms for d in deltas),
            )
        )

        decision = classify_round(
            assessment=assessment,
            contradicted=is_contradicted(assessment, round_contradiction),
            level_before=level_before,
            rounds_used=rounds_used,
            config=config,
        )
        if decision.terminal:
            return _finalize(lineage, decision, assessment)
