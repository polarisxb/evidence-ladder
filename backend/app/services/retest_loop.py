# backend/app/services/retest_loop.py
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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


from typing import Literal

from app.services.evidence_arbiter import EvidenceAssessment
from app.services.retest_policy import RetestConfig

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
