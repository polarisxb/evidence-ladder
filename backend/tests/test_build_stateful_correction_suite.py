from app.services.experiment_driver import (
    FrozenExperimentSuite,
    ModelMatrixConfig,
    compute_frozen_suite_hash,
)
from scripts.build_stateful_correction_suite import build_cases, build_model_matrix


def test_stateful_correction_suite_is_balanced_and_independent() -> None:
    cases = build_cases()

    assert len(cases) == 48
    attacks = [case for case in cases if case["variant_type"] == "attack"]
    clean = [case for case in cases if case["variant_type"] == "clean"]
    distractors = [
        case
        for case in cases
        if case["variant_type"] == "benign_distractor"
    ]
    assert (len(attacks), len(clean), len(distractors)) == (32, 8, 8)
    assert {
        case["category"]
        for case in attacks
    } == {
        "claim_without_action",
        "refusal_with_action_language",
        "discussion_only",
        "cautious_hidden_action",
    }
    assert all(
        case["ground_truth_oracle"]["oracle_type"]
        == "hidden_state_transition"
        for case in attacks
    )
    assert all(
        case["target_config"]["temperature"] == 0.7
        for case in cases
    )
    assert all("canary_tokens" not in case["target_config"] for case in cases)
    assert all("ground_truth" not in case for case in attacks)

    committed_dry_run_cases = [
        case
        for case in attacks
        if (
            case["target_config"]["builtin_probe_config"]["action_trigger"]
            == case["payload"]
        )
    ]
    assert len(committed_dry_run_cases) == 16

    suite = FrozenExperimentSuite.model_validate(
        {
            "suite_version": "retest-mvp.v1",
            "content_hash": compute_frozen_suite_hash(cases),
            "cases": cases,
        }
    )
    assert len(suite.cases) == 48


def test_stateful_correction_dry_run_matrix_is_builtin_only() -> None:
    matrix = ModelMatrixConfig.model_validate(build_model_matrix())

    assert {model.role for model in matrix.models} == {
        "target",
        "judge",
        "verifier",
    }
    assert all(model.provider_id == "builtin" for model in matrix.models)
