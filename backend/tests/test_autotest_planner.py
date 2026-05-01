from app.services.autotest_planner import build_autotest_plan


def test_small_budget_uses_low_cost_strategies() -> None:
    plan = build_autotest_plan({
        "target_type": "openai_compatible",
        "attack_categories": ["prompt_injection"],
        "budget": "small",
    })

    assert plan.budget == "small"
    assert plan.risk_categories == ("prompt_injection",)
    assert "template_scan" in plan.phases
    assert "quartet_controls" in plan.phases
    assert "pair" not in plan.strategies
    assert "tap" not in plan.strategies
    assert plan.max_retest_rounds == 1


def test_default_categories_are_used_when_all_is_requested() -> None:
    plan = build_autotest_plan({
        "target_type": "custom",
        "attack_categories": ["all"],
        "budget": "medium",
    })

    assert "prompt_injection" in plan.risk_categories
    assert "system_prompt_extraction" in plan.risk_categories
    assert "information_disclosure" in plan.risk_categories
    assert "mutation" in plan.strategies


def test_adapter_with_enabled_probe_marks_probe_available() -> None:
    plan = build_autotest_plan({
        "target_type": "adapter",
        "budget": "full",
        "adapter": {"probe_config": {"enabled": True}},
    })

    assert plan.probe_available is True
    assert "probe_verification" in plan.phases
    assert "pair" in plan.strategies
    assert "tap" in plan.strategies


def test_disabled_probe_is_not_added_to_plan() -> None:
    plan = build_autotest_plan({
        "target_type": "adapter",
        "budget": "full",
        "adapter": {"probe_config": {"enabled": False}},
    })

    assert plan.probe_available is False
    assert "probe_verification" not in plan.phases
