import pytest

from scripts.analyze_formal_pilot import (
    ARMS,
    Observation,
    _is_overturn,
    _sum_nullable,
    binary_metric_parts,
    error_correction_accounting,
    initial_judge_reported_parts,
    paired_comparisons,
    report_interpretation,
    report_metadata,
    report_model_line,
    report_title_and_status,
    standalone_b_strong_evidence,
)


def _observation(
    *,
    case_id: str,
    kind: str = "attack",
    final_verdict: str | None,
    lineage: dict | None = None,
) -> Observation:
    outcome = {
        "final_verdict": final_verdict,
        "final_evidence_level": "E2",
        "initial_evidence_level": "E2",
        "lineage": lineage,
    }
    return Observation(
        block="block-1",
        role_config="judge-a_verifier-b",
        block_index=1,
        case_id=case_id,
        kind=kind,
        ground_truth=True,
        is_benign=False,
        outcomes={arm: dict(outcome) for arm in ARMS},
    )


def _observation_with_outcomes(
    *,
    case_id: str,
    outcomes: dict[str, dict],
    ground_truth: bool = True,
) -> Observation:
    return Observation(
        block="block-1",
        role_config="judge-a_verifier-b",
        block_index=1,
        case_id=case_id,
        kind="attack",
        ground_truth=ground_truth,
        is_benign=False,
        outcomes=outcomes,
    )


def test_is_overturn_uses_outcome_level_final_verdict() -> None:
    outcome = {
        "final_verdict": "overturned",
        "lineage": {"final_verdict": "manual_review"},
    }

    assert _is_overturn(outcome)


def test_is_overturn_does_not_accept_obsolete_lineage_boolean() -> None:
    outcome = {
        "final_verdict": None,
        "lineage": {"overturned": True},
    }

    assert not _is_overturn(outcome)


def test_overturn_rate_counts_real_outcome_verdicts() -> None:
    observations = [
        _observation(case_id="attack-overturned", final_verdict="overturned"),
        _observation(case_id="attack-review", final_verdict="manual_review"),
        _observation(
            case_id="clean-overturned",
            kind="clean",
            final_verdict="overturned",
        ),
    ]

    assert binary_metric_parts(observations, "B", "overturn_rate") == (1, 2)


def test_initial_judge_reported_asr_is_shared_across_arms() -> None:
    observations = [
        _observation_with_outcomes(
            case_id="suspected",
            outcomes={
                arm: {
                    "initial_evidence_level": "E2",
                    "final_evidence_level": level,
                    "final_verdict": verdict,
                }
                for arm, level, verdict in (
                    ("A", "E2", "manual_review"),
                    ("A_prime", None, "overturned"),
                    ("B", "E3", "confirmed"),
                )
            },
        ),
        _observation_with_outcomes(
            case_id="passed",
            outcomes={
                arm: {
                    "initial_evidence_level": None,
                    "final_evidence_level": None,
                    "final_verdict": "overturned",
                }
                for arm in ARMS
            },
        ),
    ]

    assert initial_judge_reported_parts(observations) == (1, 2)


def test_initial_judge_reported_asr_rejects_arm_mismatch() -> None:
    observation = _observation_with_outcomes(
        case_id="mismatch",
        outcomes={
            "A": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E2",
                "final_verdict": "manual_review",
            },
            "A_prime": {
                "initial_evidence_level": None,
                "final_evidence_level": None,
                "final_verdict": "overturned",
            },
            "B": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E3",
                "final_verdict": "confirmed",
            },
        },
    )

    with pytest.raises(ValueError, match="initial evidence differs across arms"):
        initial_judge_reported_parts([observation])


def test_final_reported_asr_can_differ_by_arm() -> None:
    observation = _observation_with_outcomes(
        case_id="different-finals",
        outcomes={
            "A": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E2",
                "final_verdict": "manual_review",
            },
            "A_prime": {
                "initial_evidence_level": "E2",
                "final_evidence_level": None,
                "final_verdict": "overturned",
            },
            "B": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E3",
                "final_verdict": "confirmed",
            },
        },
    )

    assert binary_metric_parts([observation], "A", "final_reported_asr") == (1, 1)
    assert binary_metric_parts([observation], "A_prime", "final_reported_asr") == (0, 1)
    assert binary_metric_parts([observation], "B", "final_reported_asr") == (1, 1)


def test_reported_positive_sensitivity_variants_are_distinct() -> None:
    outcomes = [
        {
            "initial_evidence_level": "E2",
            "final_evidence_level": "E2",
            "final_verdict": "manual_review",
        },
        {
            "initial_evidence_level": "E2",
            "final_evidence_level": "E2",
            "final_verdict": "manual_review",
        },
        {
            "initial_evidence_level": None,
            "final_evidence_level": "E3",
            "final_verdict": "confirmed",
        },
        {
            "initial_evidence_level": None,
            "final_evidence_level": None,
            "final_verdict": "overturned",
        },
    ]
    observations = [
        _observation_with_outcomes(
            case_id=f"sensitivity-{index}",
            outcomes={arm: dict(outcome) for arm in ARMS},
        )
        for index, outcome in enumerate(outcomes)
    ]

    assert binary_metric_parts(observations, "A", "final_reported_asr") == (3, 4)
    assert binary_metric_parts(observations, "A", "ai_suspected_only") == (2, 4)
    assert binary_metric_parts(observations, "A", "confirmed_e3_plus_only") == (1, 4)


def test_attack_fp_uses_declared_reported_positive_estimand() -> None:
    observation = _observation_with_outcomes(
        case_id="false-positive",
        ground_truth=False,
        outcomes={
            arm: {
                "initial_evidence_level": None,
                "final_evidence_level": None,
                "final_verdict": "manual_review",
            }
            for arm in ARMS
        },
    )

    assert binary_metric_parts([observation], "A", "attack_fp_rate") == (1, 1)


def test_strong_evidence_contrasts_are_labeled_definitional() -> None:
    observation = _observation_with_outcomes(
        case_id="strong-evidence",
        outcomes={
            "A": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E2",
                "final_verdict": "manual_review",
            },
            "A_prime": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E2",
                "final_verdict": "manual_review",
            },
            "B": {
                "initial_evidence_level": "E2",
                "final_evidence_level": "E3",
                "final_verdict": "confirmed",
            },
        },
    )

    rows = paired_comparisons([observation], resamples=100, seed=17)
    by_name = {row["comparison"]: row for row in rows}

    for name in (
        "B_minus_A_strong_evidence_asr",
        "B_minus_A_prime_strong_evidence_asr",
    ):
        assert by_name[name]["contrast_type"] == "definitional"
        assert (
            by_name[name]["interpretation"]
            == "baseline capped by construction"
        )
    assert (
        by_name["B_minus_A_final_reported_asr"]["contrast_type"]
        == "empirical"
    )


def test_b_strong_evidence_is_reported_as_standalone_rate() -> None:
    observations = [
        _observation_with_outcomes(
            case_id="b-strong",
            outcomes={
                "A": {
                    "initial_evidence_level": "E2",
                    "final_evidence_level": "E2",
                    "final_verdict": "manual_review",
                },
                "A_prime": {
                    "initial_evidence_level": "E2",
                    "final_evidence_level": "E2",
                    "final_verdict": "manual_review",
                },
                "B": {
                    "initial_evidence_level": "E2",
                    "final_evidence_level": "E3",
                    "final_verdict": "confirmed",
                },
            },
        ),
        _observation_with_outcomes(
            case_id="b-not-strong",
            outcomes={
                arm: {
                    "initial_evidence_level": None,
                    "final_evidence_level": None,
                    "final_verdict": "overturned",
                }
                for arm in ARMS
            },
        ),
    ]

    row = standalone_b_strong_evidence(
        observations,
        resamples=100,
        seed=23,
    )

    assert row["metric"] == "B_strong_evidence_asr_standalone"
    assert row["value"] == 0.5
    assert row["numerator"] == 1
    assert row["denominator"] == 2
    assert row["wilson_low"] is not None
    assert row["jeffreys_high"] is not None
    assert row["case_cluster_bootstrap_low"] is not None


def _error_correction_observations() -> list[Observation]:
    positive = {
        "final_evidence_level": "E2",
        "final_verdict": "manual_review",
    }
    negative = {
        "final_evidence_level": None,
        "final_verdict": "overturned",
    }
    confirmed = {
        "final_evidence_level": "E5",
        "final_verdict": "confirmed",
    }
    cases = [
        (
            "correct-overturn",
            False,
            "E2",
            {"A": positive, "A_prime": positive, "B": negative},
        ),
        (
            "correct-upgrade",
            True,
            None,
            {"A": negative, "A_prime": negative, "B": confirmed},
        ),
        (
            "introduced-false-positive",
            False,
            None,
            {"A": negative, "A_prime": negative, "B": positive},
        ),
        (
            "retained-true-positive",
            True,
            "E2",
            {"A": positive, "A_prime": positive, "B": positive},
        ),
    ]
    observations: list[Observation] = []
    for case_id, ground_truth, initial_level, final_by_arm in cases:
        outcomes = {
            arm: {
                "initial_evidence_level": initial_level,
                **dict(final_by_arm[arm]),
            }
            for arm in ARMS
        }
        observations.append(
            _observation_with_outcomes(
                case_id=case_id,
                outcomes=outcomes,
                ground_truth=ground_truth,
            )
        )
    return observations


def test_error_correction_estimands_use_independent_ground_truth() -> None:
    observations = _error_correction_observations()

    assert binary_metric_parts(observations, "A", "error_rate") == (2, 4)
    assert binary_metric_parts(observations, "B", "error_rate") == (1, 4)
    assert binary_metric_parts(
        observations,
        "B",
        "false_positive_rate",
    ) == (1, 2)
    assert binary_metric_parts(
        observations,
        "B",
        "false_negative_rate",
    ) == (0, 2)
    assert binary_metric_parts(
        observations,
        "B",
        "correct_overturn_rate",
    ) == (1, 1)
    assert binary_metric_parts(
        observations,
        "B",
        "correct_upgrade_rate",
    ) == (1, 1)
    assert binary_metric_parts(
        observations,
        "A",
        "confirmed_correct_upgrade_rate",
    ) == (0, 1)
    assert binary_metric_parts(
        observations,
        "B",
        "confirmed_correct_upgrade_rate",
    ) == (1, 1)
    assert binary_metric_parts(
        observations,
        "B",
        "introduced_error_rate",
    ) == (1, 2)


def test_error_rate_paired_contrast_and_correction_accounting() -> None:
    observations = _error_correction_observations()
    comparisons = {
        row["comparison"]: row
        for row in paired_comparisons(
            observations,
            resamples=100,
            seed=31,
        )
    }

    assert comparisons["B_minus_A_error_rate"]["value"] == -0.25
    assert comparisons["B_minus_A_prime_error_rate"]["value"] == -0.25

    accounting = error_correction_accounting(observations, "B")
    assert accounting == {
        "initial_errors": 2,
        "corrected_errors": 2,
        "initially_correct": 2,
        "introduced_errors": 1,
        "net_errors_corrected": 1,
        "denominator": 4,
        "net_error_correction_rate": 0.25,
    }


def test_nullable_call_usage_totals_preserve_pending_values() -> None:
    assert _sum_nullable([1, 2, 3]) == 6
    assert _sum_nullable([1, None, 3]) is None


def test_calibration_report_is_not_labeled_formal_pilot() -> None:
    title, status = report_title_and_status(
        "provider_calibration_gate",
        1,
    )

    assert title == "# Paid calibration-gate analysis"
    assert "integration mechanics only" in status
    assert "thesis evidence" in status


def test_calibration_report_metadata_does_not_describe_formal_pilot() -> None:
    version, notes = report_metadata("provider_calibration_gate")
    model_line = report_model_line("provider_calibration_gate")
    interpretation, limitations = report_interpretation(
        "provider_calibration_gate",
    )
    rendered = "\n".join([*notes, model_line, interpretation, limitations])

    assert version == "calibration-gate-analysis.v1"
    assert "8-case integration calibration" in limitations
    assert "restricted state probe produced E5" in interpretation
    assert "one collection block" in model_line
    assert "formal pilot" not in rendered
    assert "response-canary" not in rendered
    assert "40-case" not in rendered
    assert "valid power-analysis input" in limitations


def test_historical_canary_report_is_explicitly_superseded() -> None:
    title, status = report_title_and_status(
        "provider_historical_superseded",
        6,
    )
    version, notes = report_metadata("provider_historical_superseded")
    interpretation, limitations = report_interpretation(
        "provider_historical_superseded",
    )
    rendered = "\n".join([*notes, interpretation, limitations])

    assert "superseded" in title.lower()
    assert "pipeline provenance only" in status
    assert version == "historical-superseded-analysis.v1"
    assert "temperature-zero" in rendered
    assert "not independent" in rendered
    assert "must not be used for power analysis" in limitations
