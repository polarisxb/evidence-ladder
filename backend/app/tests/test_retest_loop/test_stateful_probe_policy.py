from app.services.evidence_arbiter import arbitrate_evidence
from app.services.retest_policy import RetestConfig, plan_retests


def test_failed_state_probe_demotes_rule_supported_action_claim() -> None:
    assessment = arbitrate_evidence(
        {
            "variant_type": "attack",
            "verdict_status": "ai_suspected",
            "behavior_flags": {"unauthorized_action_claim": True},
            "rule_hits": [{"rule": "retest_attack_delta"}],
            "business_verification_status": "probe_failed",
        }
    )

    assert assessment.is_strong_evidence is False
    assert "text_claim_probe_failed" in assessment.conflict_types


def test_stateful_policy_probes_initial_judge_negative_attack() -> None:
    actions = plan_retests(
        {
            "variant_type": "attack",
            "verdict_status": "passed",
            "behavior_flags": {"unauthorized_action_claim": False},
        },
        RetestConfig(
            max_retest_rounds=1,
            quartet_enabled=False,
            probe_available=True,
            probe_on_no_evidence=True,
        ),
    )

    assert [action.action_type for action in actions] == ["run_probe"]
    assert actions[0].reason == "predeclared_state_probe"
