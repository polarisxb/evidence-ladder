"""Evidence-guided retest policy for AutoTest v1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.services.evidence_arbiter import arbitrate_evidence


RetestActionType = Literal["run_quartet", "run_canary_retest", "run_probe"]


@dataclass(frozen=True)
class RetestConfig:
    max_retest_rounds: int = 1
    current_retest_round: int = 0
    quartet_enabled: bool = True
    canary_enabled: bool = False
    probe_available: bool = False
    probe_on_no_evidence: bool = False


@dataclass(frozen=True)
class RetestAction:
    action_type: RetestActionType
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"action_type": self.action_type, "reason": self.reason}


def plan_retests(
    result: Mapping[str, Any],
    config: RetestConfig | None = None,
) -> tuple[RetestAction, ...]:
    """Return bounded retest actions for one result.

    Retest policy is deterministic and evidence-driven. It never triggers after
    the configured max round, and it avoids treating strong rule/probe evidence
    as something that needs more testing.
    """

    config = config or RetestConfig()
    if config.max_retest_rounds <= 0:
        return ()
    if config.current_retest_round >= config.max_retest_rounds:
        return ()

    assessment = arbitrate_evidence(result)
    if assessment.is_strong_evidence:
        return ()

    actions: list[RetestAction] = []
    conflicts = set(assessment.conflict_types)

    if config.quartet_enabled and "judge_without_rule_evidence" in conflicts:
        actions.append(RetestAction("run_quartet", "judge_without_rule_evidence"))

    if config.canary_enabled and _secret_disclosure_suspected(result):
        actions.append(RetestAction("run_canary_retest", "secret_disclosure_suspected"))

    if config.probe_available and (
        "text_claim_requires_probe" in conflicts
        or assessment.evidence_label == "text_claim_only"
    ):
        actions.append(RetestAction("run_probe", "text_claim_requires_probe"))
    elif (
        config.probe_available
        and config.probe_on_no_evidence
        and str(result.get("variant_type") or "").strip().lower() == "attack"
        and assessment.evidence_level is None
    ):
        actions.append(RetestAction("run_probe", "predeclared_state_probe"))

    return tuple(_dedupe_actions(actions))


def _secret_disclosure_suspected(result: Mapping[str, Any]) -> bool:
    flags = result.get("behavior_flags")
    if isinstance(flags, Mapping) and flags.get("secret_disclosure") is True:
        return True
    category = str(result.get("category") or "").strip()
    if category in {"system_prompt_extraction", "information_disclosure"}:
        verdict = str(result.get("verdict_status") or "").strip().lower()
        return verdict in {"ai_suspected", "manual_review_needed"}
    return False


def _dedupe_actions(actions: list[RetestAction]) -> list[RetestAction]:
    seen: set[str] = set()
    result: list[RetestAction] = []
    for action in actions:
        if action.action_type in seen:
            continue
        seen.add(action.action_type)
        result.append(action)
    return result
