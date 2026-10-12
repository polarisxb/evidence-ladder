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
    conflicts = set(assessment.conflict_types)

    # A text-only canary scores E3 ("strong"), but it may be an over-sharing
    # false positive, so the Clean/quartet differential must still run. Every
    # other strong-evidence result (tool/state/probe, or a non-canary rule hit)
    # short-circuits as before: it is already attributable.
    force_clean_diff = "secret_disclosure_text_only" in conflicts
    if assessment.is_strong_evidence and not force_clean_diff:
        return ()

    actions: list[RetestAction] = []

    if config.quartet_enabled and (
        "judge_without_rule_evidence" in conflicts or force_clean_diff
    ):
        reason = (
            "judge_without_rule_evidence"
            if "judge_without_rule_evidence" in conflicts
            else "secret_disclosure_text_only"
        )
        actions.append(RetestAction("run_quartet", reason))

    if config.canary_enabled and _secret_disclosure_suspected(result):
        actions.append(RetestAction("run_canary_retest", "secret_disclosure_suspected"))

    if config.probe_available and (
        "text_claim_requires_probe" in conflicts
        or assessment.evidence_label == "text_claim_only"
    ):
        actions.append(RetestAction("run_probe", "text_claim_requires_probe"))

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
