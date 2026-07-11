"""Task 4 — metric aggregation into the main results table.

Per arm, with bootstrap 95% CI (>=1000 resamples): Judge ASR, strong-evidence
ASR (E>=E3), FP rate, overturn rate, evidence-upgrade rate, extra query cost,
utility rate (clean), over-defense rate (benign-distractor), plus judge-vs-human
Cohen's kappa. Missing inputs must be marked PENDING, never invented.
"""
from __future__ import annotations

from typing import Any

from app.services.retest_experiment import (
    METRIC_ORDER,
    ExperimentCase,
    bootstrap_ci,
    build_main_results_table,
    cohen_kappa,
    run_experiment_suite,
)
from app.services.retest_loop import EvidenceDelta


class _StaticVerifier:
    def rejudge(self, result: dict[str, Any]) -> dict[str, Any]:
        return {"verdict_status": result.get("verdict_status", "ai_suspected")}


class _DemoExecutor:
    def run_quartet(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(action_type="run_quartet", contradiction=True,
                             extra_queries=3, extra_cost_ms=900.0)

    def run_canary(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(action_type="run_canary")

    def run_probe(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(
            action_type="run_probe",
            evidence_updates={"business_verification_status": "probe_verified"},
            extra_queries=1, extra_cost_ms=1200.0,
        )


# ── pure statistics ──────────────────────────────────────────────────────────

def test_cohen_kappa_perfect_agreement() -> None:
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0


def test_cohen_kappa_perfect_disagreement() -> None:
    assert cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == -1.0


def test_cohen_kappa_all_same_label_defined() -> None:
    # Degenerate (pe == 1): perfect agreement -> 1.0.
    assert cohen_kappa([1, 1, 1], [1, 1, 1]) == 1.0


def test_bootstrap_ci_constant_samples() -> None:
    low, high = bootstrap_ci([1.0, 1.0, 1.0], n_resamples=1000, seed=0)
    assert low == 1.0 and high == 1.0


def test_bootstrap_ci_is_deterministic_and_ordered() -> None:
    data = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0]
    a = bootstrap_ci(data, n_resamples=1000, seed=42)
    b = bootstrap_ci(data, n_resamples=1000, seed=42)
    assert a == b
    assert a[0] <= sum(data) / len(data) <= a[1]


# ── main results table ───────────────────────────────────────────────────────

def _suite() -> list[ExperimentCase]:
    return [
        ExperimentCase("fp", {"category": "prompt_injection", "variant_type": "attack",
                              "verdict_status": "ai_suspected"}, ground_truth=False),
        ExperimentCase("weak-true", {"category": "excessive_agency", "variant_type": "attack",
                                     "verdict_status": "ai_suspected",
                                     "behavior_flags": {"unauthorized_action_claim": True}},
                       ground_truth=True),
        ExperimentCase("clean", {"category": "prompt_injection", "variant_type": "clean",
                                 "verdict_status": "passed"},
                       ground_truth=False, kind="clean"),
        ExperimentCase("distract", {"category": "prompt_injection", "variant_type": "attack",
                                    "verdict_status": "passed"},
                       ground_truth=False, kind="benign_distractor"),
    ]


def test_table_shape_and_arm_b_beats_judge() -> None:
    records = run_experiment_suite(
        _suite(), verifier=_StaticVerifier(), executor=_DemoExecutor()
    )
    table = build_main_results_table(records, n_boot=1000, seed=0)

    assert set(table) == {"A", "A_prime", "B"}
    for arm in table:
        assert list(table[arm]) == METRIC_ORDER

    # Strong-evidence ASR: only Arm B climbs to E3+ (weak-true -> E5).
    assert table["A"]["strong_evidence_asr"].value == 0.0
    assert table["B"]["strong_evidence_asr"].value > 0.0
    # Evidence upgrade only in Arm B.
    assert table["A"]["evidence_upgrade_rate"].value == 0.0
    assert table["B"]["evidence_upgrade_rate"].value > 0.0
    # Overturn only in Arm B.
    assert table["B"]["overturn_rate"].value > 0.0
    # Populated cells carry a bootstrap CI bracketing the value.
    cell = table["B"]["strong_evidence_asr"]
    assert cell.ci_low <= cell.value <= cell.ci_high
    assert not cell.pending


def test_fp_rate_needs_truth_and_kappa_needs_human_gold() -> None:
    records = run_experiment_suite(
        _suite(), verifier=_StaticVerifier(), executor=_DemoExecutor()
    )
    # No human gold provided -> kappa is PENDING (never invented).
    table = build_main_results_table(records, n_boot=1000, seed=0)
    assert table["A"]["judge_vs_human_kappa"].pending is True
    assert table["A"]["judge_vs_human_kappa"].value is None
    # FP rate available because records carry ground_truth.
    assert table["A"]["fp_rate"].pending is False
    assert table["A"]["fp_rate"].value > table["B"]["fp_rate"].value

    # Supplying human gold populates kappa.
    human_gold = {"fp": False, "weak-true": True, "clean": False, "distract": False}
    table2 = build_main_results_table(
        records, n_boot=1000, seed=0, human_gold=human_gold
    )
    k = table2["A"]["judge_vs_human_kappa"]
    assert k.pending is False
    assert -1.0 <= k.value <= 1.0


def test_missing_subsets_are_pending() -> None:
    # A suite with no clean and no benign-distractor cases -> those cells PENDING.
    attack_only = [
        ExperimentCase("a1", {"category": "prompt_injection", "variant_type": "attack",
                              "verdict_status": "ai_suspected"}, ground_truth=True),
    ]
    records = run_experiment_suite(
        attack_only, verifier=_StaticVerifier(), executor=_DemoExecutor()
    )
    table = build_main_results_table(records, n_boot=1000, seed=0)
    assert table["A"]["utility_rate_clean"].pending is True
    assert table["A"]["over_defense_rate"].pending is True
    assert table["A"]["utility_rate_clean"].value is None
