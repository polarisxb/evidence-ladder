from app.services.experiment_driver import (
    FrozenExperimentSuite,
    ModelMatrixConfig,
    compute_frozen_suite_hash,
)
from scripts.build_stateful_paid_gate import build_cases, build_model_matrix


def test_paid_gate_has_balanced_hidden_state_calibration_cases() -> None:
    cases = build_cases()

    assert len(cases) == 8
    assert all(case["variant_type"] == "attack" for case in cases)
    assert all(case["target_config"]["temperature"] == 0.7 for case in cases)
    assert all(
        case["ground_truth_oracle"]["oracle_type"]
        == "hidden_state_transition"
        for case in cases
    )
    assert all("ground_truth" not in case for case in cases)
    policies = [
        case["target_config"]["stateful_sandbox_config"]["commit_policy"]
        for case in cases
    ]
    assert policies.count("always") == 4
    assert policies.count("never") == 4

    suite = FrozenExperimentSuite.model_validate(
        {
            "suite_version": "retest-mvp.v1",
            "content_hash": compute_frozen_suite_hash(cases),
            "cases": cases,
        }
    )
    assert len(suite.cases) == 8


def test_paid_gate_uses_existing_relay_target_judge_verifier() -> None:
    matrix = ModelMatrixConfig.model_validate(build_model_matrix())

    assert matrix.target_models[0].pinned_version == "gpt-5.4"
    assert matrix.judge_model.pinned_version == "gpt-5.5"
    assert matrix.verifier_model.pinned_version == "gpt-5.4"
    assert all(model.provider_id != "builtin" for model in matrix.models)
