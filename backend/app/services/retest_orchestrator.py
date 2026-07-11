"""Retest-loop orchestration for the main scan flow (P3).

Bridges a completed ``case_attempt`` (built by ``case_executor``) to the async
retest state machine and persists its :class:`RetestLineage`:

- ``build_retest_result``    — derive the arbiter/executor input mapping (pure).
- ``resolve_retest_arm``     — turn ``advanced_config`` into an experiment arm +
  ``RetestConfig`` (Arm A = judge-only baseline, Arm B = ④ retest loop). Absent
  / unknown ⇒ ``None`` (feature off) so existing scans are unaffected.
- ``run_case_retest``        — run ``run_retest_loop_async`` with a real (or
  injected) executor against the same case/target.
- ``persist_case_retest_lineage`` — write the lineage to ``case_retest_lineages``.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CaseRetestLineage
from app.services.retest_executor_real import RealRetestExecutor
from app.services.retest_loop import RetestLineage, run_retest_loop_async
from app.services.retest_policy import RetestConfig


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def build_retest_result(
    case_attempt: Mapping[str, Any], template: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Derive the retest-loop input mapping from an in-memory case_attempt.

    Mirrors the keys the evidence arbiter reads (see
    ``autotest_summary._result_payload``) plus the fields the real executor
    needs to re-send the eliciting prompt (``case_id`` / ``payload_text``).
    """
    template = template or {}
    analysis = case_attempt.get("analysis")
    behavior_flags = getattr(analysis, "behavior_flags", None) or {}
    verdict = case_attempt.get("verdict") if isinstance(case_attempt.get("verdict"), Mapping) else {}
    case_summary = (
        case_attempt.get("case_summary") if isinstance(case_attempt.get("case_summary"), Mapping) else {}
    )
    control_summary = (
        case_attempt.get("control_summary")
        if isinstance(case_attempt.get("control_summary"), Mapping)
        else {}
    )
    response_evaluation = (
        case_attempt.get("response_evaluation")
        if isinstance(case_attempt.get("response_evaluation"), Mapping)
        else {}
    )

    tool_calls = _list(case_summary.get("tool_calls")) or _list(verdict.get("tool_calls"))
    business_status = (
        case_attempt.get("business_verification_status")
        or case_summary.get("business_verification_status")
    )

    return {
        "case_id": str(case_attempt.get("case_id") or ""),
        "payload_text": str(case_attempt.get("payload_text") or ""),
        "category": str(template.get("category") or template.get("category_name") or ""),
        "variant_type": str(case_summary.get("variant_type") or "attack"),
        "verdict_status": verdict.get("verdict_status"),
        "rule_hits": _list(verdict.get("rule_hits")),
        "behavior_flags": dict(behavior_flags) if isinstance(behavior_flags, Mapping) else {},
        "control_assessment": control_summary.get("control_assessment")
        or case_summary.get("control_assessment"),
        "business_verification_status": business_status,
        "response_evaluation": dict(response_evaluation),
        "tool_calls": tool_calls,
        "tool_observed": case_summary.get("tool_observed") is True,
    }


def resolve_retest_arm(
    advanced: Mapping[str, Any] | None, *, target_type: str | None = None
) -> tuple[str, RetestConfig] | None:
    """Map ``advanced_config`` to an experiment arm + config, or ``None`` (off)."""
    advanced = advanced if isinstance(advanced, Mapping) else {}
    arm = str(advanced.get("retest_arm") or "").strip().upper()
    if arm == "A":
        return "A", RetestConfig(max_retest_rounds=0)
    if arm == "B":
        quartet_mode = str(advanced.get("quartet_mode") or "adaptive")
        return "B", RetestConfig(
            max_retest_rounds=int(advanced.get("max_retest_rounds") or 2),
            quartet_enabled=quartet_mode != "off",
            canary_enabled=True,
            probe_available=target_type == "adapter",
        )
    return None


async def run_case_retest(
    *,
    task: Any,
    template: Mapping[str, Any],
    case_attempt: Mapping[str, Any],
    config: RetestConfig,
    executor: Any | None = None,
) -> RetestLineage:
    result = build_retest_result(case_attempt, template)
    executor = executor if executor is not None else RealRetestExecutor(task, template)
    return await run_retest_loop_async(result, executor, config)


async def persist_case_retest_lineage(
    db: AsyncSession,
    *,
    task: Any,
    case_id: str,
    arm: str | None,
    retest_reason: str | None,
    lineage: RetestLineage,
    auto_commit: bool = True,
) -> CaseRetestLineage:
    row = CaseRetestLineage(
        scan_task_id=task.id,
        case_id=case_id,
        arm=arm,
        retest_reason=retest_reason,
        initial_evidence_level=lineage.initial_evidence_level,
        final_evidence_level=lineage.final_evidence_level,
        final_verdict=lineage.final_verdict,
        converged_reason=lineage.converged_reason,
        total_extra_queries=lineage.total_extra_queries,
        total_extra_cost_ms=lineage.total_extra_cost_ms,
        lineage_json=lineage.to_dict(),
    )
    db.add(row)
    if auto_commit:
        await db.commit()
    else:
        await db.flush()
    return row
