from app.services.retest_policy import RetestConfig, plan_retests


def test_judge_only_success_triggers_quartet_retest() -> None:
    actions = plan_retests(
        {
            "verdict_status": "ai_suspected",
            "rule_hits": [],
            "behavior_flags": {},
        },
        RetestConfig(quartet_enabled=True),
    )

    assert [a.action_type for a in actions] == ["run_quartet"]
    assert actions[0].reason == "judge_without_rule_evidence"


def test_secret_disclosure_suspicion_triggers_canary_retest() -> None:
    actions = plan_retests(
        {
            "verdict_status": "ai_suspected",
            "category": "system_prompt_extraction",
            "behavior_flags": {"secret_disclosure": True},
        },
        RetestConfig(canary_enabled=True),
    )

    assert any(a.action_type == "run_canary_retest" for a in actions)


def test_text_claim_triggers_probe_when_available() -> None:
    actions = plan_retests(
        {
            "verdict_status": "ai_suspected",
            "behavior_flags": {"unauthorized_action_claim": True},
        },
        RetestConfig(probe_available=True),
    )

    assert any(a.action_type == "run_probe" for a in actions)


def test_max_retest_rounds_zero_disables_actions() -> None:
    actions = plan_retests(
        {
            "verdict_status": "ai_suspected",
            "rule_hits": [],
        },
        RetestConfig(max_retest_rounds=0, quartet_enabled=True),
    )

    assert actions == ()


def test_strong_rule_evidence_does_not_trigger_retest() -> None:
    actions = plan_retests(
        {
            "verdict_status": "passed",
            "rule_hits": [{"rule": "canary_token_match"}],
        },
        RetestConfig(quartet_enabled=True, canary_enabled=True, probe_available=True),
    )

    assert actions == ()
