"""Build scan drafts from AutoTest plans.

AutoTest v1 keeps the agentic decision layer deterministic: the service turns
budget and evidence options into the existing ScanCreate contract, then the
normal scan API remains responsible for provider validation and execution.
"""

from __future__ import annotations

from app.schemas.autotest import AutoTestDraftRequest
from app.schemas.scan import AdvancedConfig, ScanCreate, TargetConfig
from app.services.autotest_planner import AutoTestPlan, build_autotest_plan


MUTATION_STRATEGIES: tuple[str, ...] = (
    "base64_instruction",
    "markdown_injection",
    "json_wrapper",
    "policy_shadowing",
)


def build_autotest_scan_draft(body: AutoTestDraftRequest) -> tuple[AutoTestPlan, ScanCreate]:
    """Return the inspected AutoTest plan and a compatible ScanCreate draft."""

    plan = build_autotest_plan(body.model_dump(exclude_none=True))
    scan = ScanCreate(
        name=(body.name or f"AutoTest {plan.budget} evidence scan").strip(),
        target_type=body.target_type,
        target_url=_target_url(body),
        adapter_id=body.adapter_id,
        target_config=_target_config(body),
        runtime_vars=body.runtime_vars,
        attack_categories=list(plan.risk_categories),
        advanced=_advanced_config(plan, quartet_enabled=body.enable_quartet),
        judge_provider_id=body.judge_provider_id,
        judge_model=body.judge_model,
        generation_provider_id=body.generation_provider_id,
        generation_model=body.generation_model,
    )
    return plan, scan


def _target_url(body: AutoTestDraftRequest) -> str:
    if body.target_type == "builtin_vulnerable":
        return body.target_url.strip() or "builtin"
    if body.target_type == "adapter":
        return body.target_url.strip()
    return body.target_url.strip()


def _target_config(body: AutoTestDraftRequest) -> TargetConfig | None:
    if body.target_config is None:
        if body.target_type == "builtin_vulnerable":
            return TargetConfig(vulnerable_level=2)
        return None

    config = body.target_config.model_copy(deep=True)
    if body.target_type == "builtin_vulnerable" and config.vulnerable_level is None:
        config.vulnerable_level = 2
    return config


def _advanced_config(plan: AutoTestPlan, *, quartet_enabled: bool) -> AdvancedConfig:
    budget = plan.budget
    enable_mutations = "mutation" in plan.strategies
    enable_advanced_attacks = budget == "full"

    return AdvancedConfig(
        enable_crescendo=enable_advanced_attacks,
        enable_tap=enable_advanced_attacks,
        enable_pair=enable_advanced_attacks,
        enable_self_explanation=False,
        enable_mutations=enable_mutations,
        quartet_mode=_quartet_mode(budget, quartet_enabled=quartet_enabled),
        parallel_attacks={"small": 2, "medium": 3, "full": 4}[budget],
        crescendo_max_turns=8 if enable_advanced_attacks else 5,
        tap_branching_factor=4,
        tap_max_depth=8 if enable_advanced_attacks else 5,
        pair_max_rounds=12 if enable_advanced_attacks else 5,
        mutation_strategies=list(MUTATION_STRATEGIES) if enable_mutations else [],
    )


def _quartet_mode(budget: str, *, quartet_enabled: bool) -> str:
    if not quartet_enabled:
        return "off"
    if budget == "small":
        return "full"
    return "adaptive"
