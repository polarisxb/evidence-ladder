"""AutoTest plan generation.

The first version is intentionally deterministic. It turns target settings and
budget into a bounded plan that can be inspected, tested, and later executed by
the scan runner without relying on free-form LLM decisions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


Budget = Literal["small", "medium", "full"]

DEFAULT_RISK_CATEGORIES: tuple[str, ...] = (
    "prompt_injection",
    "system_prompt_extraction",
    "information_disclosure",
    "jailbreak",
)


@dataclass(frozen=True)
class AutoTestPlan:
    target_type: str
    budget: Budget
    risk_categories: tuple[str, ...]
    strategies: tuple[str, ...]
    phases: tuple[str, ...]
    probe_available: bool
    max_retest_rounds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "budget": self.budget,
            "risk_categories": list(self.risk_categories),
            "strategies": list(self.strategies),
            "phases": list(self.phases),
            "probe_available": self.probe_available,
            "max_retest_rounds": self.max_retest_rounds,
        }


def build_autotest_plan(config: Mapping[str, Any]) -> AutoTestPlan:
    """Build a deterministic AutoTest v1 plan from user/target config."""

    target_type = str(config.get("target_type") or "openai_compatible").strip()
    budget = _budget(config.get("budget"))
    risk_categories = _risk_categories(config.get("attack_categories"))
    probe_available = _probe_available(config)

    strategies = _strategies_for_budget(budget)
    phases = _phases_for_budget(
        budget,
        quartet_enabled=config.get("enable_quartet") is not False,
        canary_enabled=config.get("enable_canary") is not False,
        probe_available=probe_available,
    )

    max_retest_rounds = config.get("max_retest_rounds")
    if not isinstance(max_retest_rounds, int):
        max_retest_rounds = 2 if budget == "full" else 1

    return AutoTestPlan(
        target_type=target_type,
        budget=budget,
        risk_categories=risk_categories,
        strategies=strategies,
        phases=phases,
        probe_available=probe_available,
        max_retest_rounds=max(0, max_retest_rounds),
    )


def _budget(value: Any) -> Budget:
    normalized = str(value or "medium").strip().lower()
    if normalized in {"small", "medium", "full"}:
        return normalized  # type: ignore[return-value]
    return "medium"


def _risk_categories(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or "all" in value:
        return DEFAULT_RISK_CATEGORIES
    categories = [str(item).strip() for item in value if str(item).strip()]
    return tuple(dict.fromkeys(categories)) or DEFAULT_RISK_CATEGORIES


def _probe_available(config: Mapping[str, Any]) -> bool:
    for key in ("adapter", "adapter_payload"):
        adapter = config.get(key)
        if isinstance(adapter, Mapping):
            probe_config = adapter.get("probe_config")
            if isinstance(probe_config, Mapping):
                return probe_config.get("enabled") is not False
    probe_config = config.get("probe_config")
    if isinstance(probe_config, Mapping):
        return probe_config.get("enabled") is not False
    return False


def _strategies_for_budget(budget: Budget) -> tuple[str, ...]:
    if budget == "small":
        return ("template", "quartet")
    if budget == "medium":
        return ("template", "quartet", "mutation")
    return ("template", "quartet", "mutation", "crescendo", "pair", "tap")


def _phases_for_budget(
    budget: Budget,
    *,
    quartet_enabled: bool,
    canary_enabled: bool,
    probe_available: bool,
) -> tuple[str, ...]:
    phases = ["health_check", "template_scan"]
    if quartet_enabled:
        phases.append("quartet_controls")
    if canary_enabled and budget in {"medium", "full"}:
        phases.append("canary_retest")
    if budget == "full":
        phases.append("advanced_attacks")
    if probe_available:
        phases.append("probe_verification")
    phases.append("summary")
    return tuple(phases)
