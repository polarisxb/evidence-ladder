import pytest

from app.schemas.autotest import AutoTestDraftRequest
from app.services.autotest_scan_builder import build_autotest_scan_draft


def test_small_builtin_draft_uses_bounded_template_scan() -> None:
    plan, scan = build_autotest_scan_draft(AutoTestDraftRequest(
        name="Evidence smoke",
        target_type="builtin_vulnerable",
        attack_categories=["jailbreak"],
        budget="small",
    ))

    assert plan.budget == "small"
    assert scan.name == "Evidence smoke"
    assert scan.target_type == "builtin_vulnerable"
    assert scan.target_url == "builtin"
    assert scan.attack_categories == ["jailbreak"]
    assert scan.target_config is not None
    assert scan.target_config.vulnerable_level == 2
    assert scan.advanced is not None
    assert scan.advanced.quartet_mode == "full"
    assert scan.advanced.enable_mutations is False
    assert scan.advanced.enable_pair is False
    assert scan.advanced.enable_tap is False


def test_full_adapter_draft_enables_advanced_evidence_strategies() -> None:
    plan, scan = build_autotest_scan_draft(AutoTestDraftRequest(
        target_type="adapter",
        adapter_id="adapter-1",
        adapter={"probe_config": {"enabled": True}},
        budget="full",
        enable_probe=True,
    ))

    assert plan.probe_available is True
    assert "probe_verification" in plan.phases
    assert scan.target_type == "adapter"
    assert scan.adapter_id == "adapter-1"
    assert scan.advanced is not None
    assert scan.advanced.quartet_mode == "adaptive"
    assert scan.advanced.enable_mutations is True
    assert scan.advanced.enable_crescendo is True
    assert scan.advanced.enable_pair is True
    assert scan.advanced.enable_tap is True
    assert scan.advanced.parallel_attacks == 4


def test_quartet_can_be_disabled_in_draft() -> None:
    plan, scan = build_autotest_scan_draft(AutoTestDraftRequest(
        target_type="openai_compatible",
        budget="medium",
        enable_quartet=False,
    ))

    assert "quartet_controls" not in plan.phases
    assert scan.advanced is not None
    assert scan.advanced.quartet_mode == "off"
    assert scan.advanced.enable_mutations is True


def test_adapter_draft_requires_adapter_id() -> None:
    with pytest.raises(ValueError, match="adapter_id is required"):
        AutoTestDraftRequest(target_type="adapter")
