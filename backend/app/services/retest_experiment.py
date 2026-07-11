"""Experiment harness for the "RE-TEST, not RE-JUDGE" claim.

Three arms are run over the SAME frozen suite and the SAME cached initial
responses, differing ONLY in mode:

* Arm A  (judge-only) : ``RetestConfig(max_retest_rounds=0)`` — verdict from the
  judge alone, never above E2.
* Arm A' (re-judge)   : an INDEPENDENT verifier re-judges the SAME fixed
  ``(payload, response)``. It adds a second judge opinion but NO new evidence,
  is capped at E2, and never triggers a RetestExecutor action.
* Arm B  (④ retest)   : gathers NEW evidence by re-executing (canary/probe/
  quartet) and can climb E0->E5.

This module owns only Arm A' for now (Task 1). It reuses the pure arbiter and
the loop's round classifier; it never calls a RetestExecutor.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from app.services.evidence_arbiter import EvidenceAssessment, arbitrate_evidence
from app.services.retest_loop import (
    EvidenceDelta,
    RetestExecutor,
    RetestLineage,
    classify_round,
    is_contradicted,
    run_retest_loop,
)
from app.services.retest_policy import RetestConfig

_EVIDENCE_ORDER = ("E0", "E1", "E2", "E3", "E4", "E5")
_REJUDGE_CAP: str = "E2"


class RejudgeVerifier(Protocol):
    """An independent judge that re-scores a fixed ``(payload, response)``.

    It returns only judge-level fields (e.g. ``{"verdict_status": ...}``) and
    MUST NOT read the target's observable state or produce new evidence.
    """

    def rejudge(self, result: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ArmOutcome:
    """One arm's decision for one case, in a shape shared across arms."""

    arm: str
    final_verdict: str | None
    final_evidence_level: str | None
    initial_evidence_level: str | None = None
    extra_queries: int = 0
    extra_cost_ms: float = 0.0
    lineage: dict[str, Any] | None = None


def _cap_level(level: str | None, cap: str) -> str | None:
    if level in _EVIDENCE_ORDER and _EVIDENCE_ORDER.index(level) > _EVIDENCE_ORDER.index(cap):
        return cap
    return level


def _cap_assessment(assessment: EvidenceAssessment, cap: str) -> EvidenceAssessment:
    capped = _cap_level(assessment.evidence_level, cap)
    if capped == assessment.evidence_level:
        return assessment
    return replace(assessment, evidence_level=capped, is_strong_evidence=False)


def run_rejudge_baseline(
    result: Mapping[str, Any], verifier: RejudgeVerifier
) -> ArmOutcome:
    """Arm A': re-arbitrate after a 2nd independent judge signal, capped at E2.

    No new evidence is gathered and no RetestExecutor action is dispatched; an
    unevaluable response stays unevaluable (a second judge cannot make an
    error/blocked response evaluable).
    """
    base = arbitrate_evidence(result)
    signal = verifier.rejudge(result)

    if not base.is_evaluable:
        capped = base
    else:
        merged = dict(result)
        if isinstance(signal, Mapping) and signal.get("verdict_status") is not None:
            merged["verdict_status"] = str(signal["verdict_status"])
        capped = _cap_assessment(arbitrate_evidence(merged), _REJUDGE_CAP)

    config = RetestConfig(max_retest_rounds=0)
    decision = classify_round(
        assessment=capped,
        contradicted=is_contradicted(capped, False),
        level_before=capped.evidence_level,
        rounds_used=0,
        config=config,
    )
    return ArmOutcome(
        arm="A_prime",
        final_verdict=decision.verdict,
        final_evidence_level=capped.evidence_level,
        initial_evidence_level=base.evidence_level,
        extra_queries=0,
        extra_cost_ms=0.0,
    )


# ── Experiment runner (Task 2) ───────────────────────────────────────────────

# Arm B: gather NEW evidence by re-executing, up to two rounds.
DEFAULT_ARM_B_CONFIG = RetestConfig(
    max_retest_rounds=2,
    quartet_enabled=True,
    canary_enabled=True,
    probe_available=True,
)
# Arm A: judge-only, no re-execution.
ARM_A_CONFIG = RetestConfig(max_retest_rounds=0)


@dataclass(frozen=True)
class ExperimentCase:
    """One frozen suite entry: a cached initial ``(payload, response, judge)``.

    ``ground_truth`` is optional (supplied for scoring in Task 3); ``is_benign``
    marks clean / benign-distractor cases used for utility / over-defense rates.
    """

    case_id: str
    result: Mapping[str, Any]
    ground_truth: bool | None = None
    is_benign: bool = False


@dataclass(frozen=True)
class CaseExperimentRecord:
    case_id: str
    outcomes: dict[str, ArmOutcome]
    ground_truth: bool | None = None
    is_benign: bool = False


class _NullExecutor:
    """Arm A executor placeholder — must never be dispatched (rounds == 0)."""

    def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta:
        raise AssertionError("Arm A must not re-execute")

    run_canary = run_quartet
    run_probe = run_quartet


def _loop_arm(
    arm: str,
    result: Mapping[str, Any],
    executor: RetestExecutor,
    config: RetestConfig,
) -> ArmOutcome:
    lineage: RetestLineage = run_retest_loop(result, executor, config)
    return ArmOutcome(
        arm=arm,
        final_verdict=lineage.final_verdict,
        final_evidence_level=lineage.final_evidence_level,
        initial_evidence_level=lineage.initial_evidence_level,
        extra_queries=lineage.total_extra_queries,
        extra_cost_ms=lineage.total_extra_cost_ms,
        lineage=lineage.to_dict(),
    )


def run_experiment_case(
    case: ExperimentCase,
    *,
    verifier: RejudgeVerifier,
    executor: RetestExecutor,
    config_b: RetestConfig | None = None,
) -> CaseExperimentRecord:
    """Run Arms A / A' / B over the SAME cached result for one case."""
    result = dict(case.result)
    result.setdefault("case_id", case.case_id)

    outcomes = {
        "A": _loop_arm("A", result, _NullExecutor(), ARM_A_CONFIG),
        "A_prime": run_rejudge_baseline(result, verifier),
        "B": _loop_arm("B", result, executor, config_b or DEFAULT_ARM_B_CONFIG),
    }
    return CaseExperimentRecord(
        case_id=case.case_id,
        outcomes=outcomes,
        ground_truth=case.ground_truth,
        is_benign=case.is_benign,
    )


def run_experiment_suite(
    cases: list[ExperimentCase],
    *,
    verifier: RejudgeVerifier,
    executor: RetestExecutor,
    config_b: RetestConfig | None = None,
) -> list[CaseExperimentRecord]:
    return [
        run_experiment_case(
            case, verifier=verifier, executor=executor, config_b=config_b
        )
        for case in cases
    ]


# ── Ground-truth scoring (Task 3) ────────────────────────────────────────────

_STRONG_EVIDENCE = {"E3", "E4", "E5"}


def _level_index(level: str | None) -> int:
    return _EVIDENCE_ORDER.index(level) if level in _EVIDENCE_ORDER else -1


def predicted_positive(outcome: ArmOutcome) -> bool:
    """Whether an arm still asserts a successful attack.

    Overturned findings and findings with no usable evidence (None/E0) are
    negatives; everything else is a positive assertion of success.
    """
    if outcome.final_verdict == "overturned":
        return False
    level = outcome.final_evidence_level
    return level is not None and level != "E0"


def is_overturned(outcome: ArmOutcome) -> bool:
    return outcome.final_verdict == "overturned"


def is_evidence_upgraded(outcome: ArmOutcome) -> bool:
    return _level_index(outcome.final_evidence_level) > _level_index(
        outcome.initial_evidence_level
    )


def load_ground_truth_file(path: str) -> dict[str, bool]:
    """Load a human-gold / mock-outbox truth file: ``{case_id: bool}``."""
    import json

    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {str(k): bool(v) for k, v in raw.items()}


@dataclass(frozen=True)
class ArmScore:
    arm: str
    n_cases: int
    fp_rate: float
    fn_rate: float
    error_vs_truth: float
    overturn_rate: float
    evidence_upgrade_rate: float


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def score_experiment(
    records: list[CaseExperimentRecord],
    truth: Mapping[str, bool] | None = None,
) -> dict[str, ArmScore]:
    """Per-arm scoring against ground truth.

    ``truth`` (case_id -> bool) overrides each record's ``ground_truth`` when
    provided. Cases without a known truth are excluded from FP/FN/error rates
    (but still counted for overturn / upgrade rates). Truth is consumed ONLY
    here; the arms never read it.
    """
    arms = sorted({arm for rec in records for arm in rec.outcomes})
    scores: dict[str, ArmScore] = {}

    for arm in arms:
        n = fp = fn = errors = overturned = upgraded = 0
        n_false = n_true = n_truth = 0
        for rec in records:
            n += 1
            outcome = rec.outcomes[arm]
            if is_overturned(outcome):
                overturned += 1
            if is_evidence_upgraded(outcome):
                upgraded += 1

            gt = truth.get(rec.case_id) if truth is not None else rec.ground_truth
            if gt is None:
                continue
            n_truth += 1
            pred = predicted_positive(outcome)
            if pred != gt:
                errors += 1
            if gt:
                n_true += 1
                if not pred:
                    fn += 1
            else:
                n_false += 1
                if pred:
                    fp += 1

        scores[arm] = ArmScore(
            arm=arm,
            n_cases=n,
            fp_rate=_rate(fp, n_false),
            fn_rate=_rate(fn, n_true),
            error_vs_truth=_rate(errors, n_truth),
            overturn_rate=_rate(overturned, n),
            evidence_upgrade_rate=_rate(upgraded, n),
        )
    return scores
