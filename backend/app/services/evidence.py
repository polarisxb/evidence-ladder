"""Evidence data model (Phase 2 of the verdict architecture rollout).

Phase 2 is a **contract-only** phase: we introduce ``Evidence`` and
``Verdict`` dataclasses plus a ``legacy_classify_verdict_as_evidence``
adapter that packages the existing ``classify_verdict`` output into
that contract. **Runtime behaviour is unchanged** — nothing in the
production pipeline calls this module yet. Phase 3 will start populating
``evidence_chain`` from independent ``Collector`` classes; Phase 4 will
replace the inner call to ``classify_verdict``.

Design references:
- ``docs/dev-notes/verdict_architecture_design.zh-CN.md`` §6 data models
- ``docs/dev-notes/verdict_architecture_rollout.zh-CN.md`` §2

Two hard constraints this module must honour:

1. The output ``Verdict.status`` must equal the legacy
   ``classify_verdict``'s ``verdict_status`` for the same input, so
   downstream code (``finding_classifier``, ``compute_posture_metrics``,
   serializers) keeps working unchanged.
2. ``Evidence`` objects are ``frozen`` so they can never be mutated in
   place; a Collector that wants to refine an evidence item must emit a
   new one. This is what lets the future ``Arbiter`` reason about the
   set of evidence without worrying about hidden state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from app.schemas.report import AnalysisResult
from app.services.verdict_engine import classify_verdict


# ---------------------------------------------------------------------------
# Public type vocabulary
# ---------------------------------------------------------------------------

EvidenceSource = Literal[
    # Hard rule matches — highest strength signals.
    "rule_hit_canary",
    "rule_hit_prompt_overlap",
    # AI judge verdict (blackbox_outcome + confidence).
    "ai_judge",
    # Behavior flags from analysis (secret_disclosure, attack_obedience, ...).
    "behavior_flag",
    # Control variant delta (discussion_supported / attack_delta_supported).
    "control_comparison",
    # Known refusal templates (Phase 1 ``refusal_signatures`` library).
    "refusal_signature",
    # Business verification probes (adapter targets only).
    "probe_verification",
    # Response screener outcome (not_evaluable short-circuit).
    "response_screener",
    # Semantic pattern layer (planned for later phases).
    "semantic_pattern",
    # Transitional wrapper used by Phase 2 adapter until Collectors land.
    "legacy_verdict_engine",
]

EvidenceDirection = Literal[
    "attack_success",    # evidence argues the target compromised
    "defense_success",   # evidence argues the target defended
    "inconclusive",      # evidence exists but cannot argue either side
]

EvidenceStrength = Literal[
    "hard",       # ~certain (canary, probe verified)
    "strong",     # high confidence single signal
    "moderate",   # mid confidence, needs consensus
    "weak",       # noise-level, cannot drive a verdict alone
]


# Statuses the arbiter may emit. Kept aligned with
# ``verdict_engine.VerdictStatus`` so downstream consumers don't need to
# know about the architecture split.
VerdictStatus = Literal[
    "passed",
    "rule_verified",
    "manual_verified",
    "ai_suspected",
    "manual_review_needed",
    "false_positive",
    "not_evaluable",
]


# Sub-category for ``needs_review`` results, used by Phase 4 Arbiter to
# tell the UI *why* the case landed on the human queue. Phase 2 adapter
# always emits ``None`` because legacy ``classify_verdict`` does not
# distinguish these paths — but the field exists now so Collectors and
# Arbiter can fill it without schema churn later.
NeedsReviewCategory = Literal[
    "conflict",        # opposing strong evidence on both sides
    "weak_signals",    # nothing strong enough in either direction
    "collector_error", # a Collector raised and was skipped
    "fallback",        # nothing matched any rule
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    """A single piece of evidence emitted by a Collector.

    Collectors produce zero-to-many Evidence objects per case. The
    Arbiter later applies R1-R8 rules to the full list.

    ``confidence`` is the *source's* self-rated confidence for this
    specific piece of evidence (``0.0``-``1.0``); it is **not** the same
    as the final ``Verdict.confidence`` which is the Arbiter's fusion of
    the whole chain.
    """

    source: EvidenceSource
    direction: EvidenceDirection
    strength: EvidenceStrength
    confidence: float
    rationale: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence (``evidence_chain_json`` column)."""
        return {
            "source": self.source,
            "direction": self.direction,
            "strength": self.strength,
            "confidence": float(self.confidence),
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Verdict:
    """Arbiter output wrapping the per-case decision.

    ``status`` and ``reason`` are what the downstream pipeline already
    understands (they mirror the legacy ``classify_verdict`` keys). The
    extra fields — ``evidence_chain``, ``needs_review_category``,
    ``arbiter_rule_hit`` — are new surface area that Phase 4+ will fill.
    """

    status: VerdictStatus
    confidence: float
    reason: str
    evidence_chain: tuple[Evidence, ...] = ()
    needs_review_category: NeedsReviewCategory | None = None
    arbiter_rule_hit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict_status": self.status,
            "verdict_confidence": float(self.confidence),
            "verdict_reason": self.reason,
            "evidence_chain": [e.to_dict() for e in self.evidence_chain],
            "needs_review_category": self.needs_review_category,
            "arbiter_rule_hit": self.arbiter_rule_hit,
        }


# ---------------------------------------------------------------------------
# Legacy adapter
# ---------------------------------------------------------------------------


# Mapping from legacy ``verdict_status`` to ``(direction, strength)`` for
# the single wrapped evidence. Chosen conservatively so a future Arbiter
# that re-reads these evidences still gets the same verdict back.
_LEGACY_STATUS_TO_EVIDENCE_PROFILE: dict[VerdictStatus, tuple[EvidenceDirection, EvidenceStrength]] = {
    # Hard rule hits — canary/prompt overlap. Arbiter R2 will match on
    # ``(attack_success, hard)``.
    "rule_verified": ("attack_success", "hard"),
    # AI judge says attack landed but no hard proof — R4 strong attack.
    "ai_suspected": ("attack_success", "strong"),
    # Analyst manually confirmed — treated as hard evidence.
    "manual_verified": ("attack_success", "hard"),
    # Defense passed with strong corroboration (high confidence or
    # refusal signature + discussion supported).
    "passed": ("defense_success", "strong"),
    # Needs review: we genuinely have no strong signal in either
    # direction yet. Record it as inconclusive so the Arbiter can apply
    # R6/R7 without mistaking this evidence as a vote.
    "manual_review_needed": ("inconclusive", "moderate"),
    # Response screener already terminated this case.
    "not_evaluable": ("inconclusive", "hard"),
    # Probe/analyst downgraded from finding to FP.
    "false_positive": ("defense_success", "hard"),
}


def _rule_hits_to_evidence(rule_hits: list[dict[str, Any]]) -> list[Evidence]:
    """Upgrade the legacy ``rule_hits`` list to typed Evidence objects.

    Canary matches and prompt-overlap matches already live in this list
    in the legacy output, so for Phase 2 we peel them out into proper
    ``Evidence`` records alongside the wrapped verdict. Phase 3 will
    replace this with a dedicated ``RuleHitCollector``.
    """

    result: list[Evidence] = []
    for hit in rule_hits or []:
        if not isinstance(hit, Mapping):
            continue
        rule = str(hit.get("rule") or "").strip()
        evidence_text = str(hit.get("evidence") or "").strip()
        if rule == "canary_token_match":
            source: EvidenceSource = "rule_hit_canary"
        elif rule == "system_prompt_overlap":
            source = "rule_hit_prompt_overlap"
        else:
            # Unknown rule name from a future verdict_engine extension;
            # still surface it, just under the generic legacy tag.
            source = "legacy_verdict_engine"
        result.append(
            Evidence(
                source=source,
                direction="attack_success",
                strength="hard",
                confidence=1.0,
                rationale=evidence_text or f"Rule match: {rule}",
                metadata={"rule": rule},
            )
        )
    return result


def legacy_classify_verdict_as_evidence(
    *,
    attack_payload: str,
    target_response: str,
    analysis: AnalysisResult,
    target_config: dict | None = None,
    control_assessment: str | None = None,
) -> Verdict:
    """Call the existing ``classify_verdict`` and re-package as ``Verdict``.

    Equivalence guarantee: for every input, the returned ``Verdict``'s
    ``status`` equals the dict's ``verdict_status`` and ``reason`` equals
    the dict's ``verdict_reason``. Tests in ``test_evidence.py`` lock
    this on a spread of 10+ real-shaped analyses.
    """

    legacy = classify_verdict(
        attack_payload=attack_payload,
        target_response=target_response,
        analysis=analysis,
        target_config=target_config,
        control_assessment=control_assessment,
    )

    status: VerdictStatus = legacy["verdict_status"]  # type: ignore[assignment]
    reason: str = legacy["verdict_reason"]
    rule_hits = legacy.get("rule_hits") or []

    # Start with any hard rule evidence the legacy engine already found.
    chain: list[Evidence] = _rule_hits_to_evidence(rule_hits)

    # Add one summary evidence that represents "what the legacy engine
    # thought overall". This is the ``legacy_verdict_engine`` tag so
    # future Arbiter code can distinguish Phase 2 wrappers from real
    # Collector output.
    direction, strength = _LEGACY_STATUS_TO_EVIDENCE_PROFILE.get(
        status, ("inconclusive", "weak")
    )

    metadata: dict[str, Any] = {
        "legacy_status": status,
        "legacy_reason": reason,
    }
    matched_sig = legacy.get("matched_refusal_signature")
    if isinstance(matched_sig, str) and matched_sig:
        metadata["matched_refusal_signature"] = matched_sig

    # For the summary evidence, use the judge confidence as the best
    # available scalar; fall back to 1.0 for hard rule verdicts.
    judge_confidence = float(getattr(analysis, "confidence", 0.0) or 0.0)
    summary_confidence = 1.0 if strength == "hard" else judge_confidence

    chain.append(
        Evidence(
            source="legacy_verdict_engine",
            direction=direction,
            strength=strength,
            confidence=summary_confidence,
            rationale=reason,
            metadata=metadata,
        )
    )

    return Verdict(
        status=status,
        confidence=summary_confidence,
        reason=reason,
        evidence_chain=tuple(chain),
        needs_review_category=None,
        arbiter_rule_hit=None,
    )
