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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import AttackCase, AttackResult, CaseRetestLineage
from app.services.retest_executor_real import RealRetestExecutor
from app.services.retest_loop import RetestLineage, run_retest_loop_async
from app.services.retest_policy import RetestConfig

_VERDICTS = ("confirmed", "overturned", "manual_review", "not_evaluable")


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


def _retest_conclusion(arm: str | None, lineage: RetestLineage) -> dict[str, Any]:
    """Non-destructive summary of a retest lineage for main-report annotation."""
    return {
        "arm": arm,
        "initial_evidence_level": lineage.initial_evidence_level,
        "final_evidence_level": lineage.final_evidence_level,
        "final_verdict": lineage.final_verdict,
        "converged_reason": lineage.converged_reason,
        "total_extra_queries": lineage.total_extra_queries,
        "total_extra_cost_ms": lineage.total_extra_cost_ms,
    }


async def apply_retest_writeback(
    db: AsyncSession,
    *,
    task: Any,
    case_id: str,
    arm: str | None,
    lineage: RetestLineage,
    auto_commit: bool = True,
) -> bool:
    """Annotate the case's main rows with the retest conclusion (non-destructive).

    Writes ``retest`` into ``AttackResult.analysis_raw`` and
    ``AttackCase.summary_json`` so the report layer can surface the ④ retest
    verdict/evidence/cost. Original headline fields (``attack_successful``,
    ``risk_level``, counts) are left untouched. No-op if the case row is absent.
    """
    case = (
        await db.execute(
            select(AttackCase).where(
                AttackCase.id == case_id, AttackCase.scan_task_id == task.id
            )
        )
    ).scalar_one_or_none()
    if case is None:
        return False

    conclusion = _retest_conclusion(arm, lineage)

    summary = dict(case.summary_json) if isinstance(case.summary_json, dict) else {}
    summary["retest"] = conclusion
    case.summary_json = summary
    flag_modified(case, "summary_json")

    if case.legacy_attack_result_id:
        result = (
            await db.execute(
                select(AttackResult).where(
                    AttackResult.id == case.legacy_attack_result_id
                )
            )
        ).scalar_one_or_none()
        if result is not None:
            raw = dict(result.analysis_raw) if isinstance(result.analysis_raw, dict) else {}
            raw["retest"] = conclusion
            result.analysis_raw = raw
            flag_modified(result, "analysis_raw")

    if auto_commit:
        await db.commit()
    else:
        await db.flush()
    return True


async def aggregate_retest_experiment(
    db: AsyncSession, scan_id: str
) -> dict[str, dict[str, Any]]:
    """Group one scan's retest lineages by experiment arm for A/B comparison.

    Returns ``{arm: {total, verdicts{...}, total_extra_queries,
    total_extra_cost_ms, mean_extra_queries, mean_extra_cost_ms}}`` — only arms
    that produced lineages appear.
    """
    rows = (
        (
            await db.execute(
                select(CaseRetestLineage).where(
                    CaseRetestLineage.scan_task_id == scan_id
                )
            )
        )
        .scalars()
        .all()
    )

    metrics: dict[str, dict[str, Any]] = {}
    for row in rows:
        arm = row.arm or "unknown"
        bucket = metrics.setdefault(
            arm,
            {
                "total": 0,
                "verdicts": {v: 0 for v in _VERDICTS},
                "total_extra_queries": 0,
                "total_extra_cost_ms": 0.0,
            },
        )
        bucket["total"] += 1
        verdict = row.final_verdict or "manual_review"
        bucket["verdicts"][verdict] = bucket["verdicts"].get(verdict, 0) + 1
        bucket["total_extra_queries"] += int(row.total_extra_queries or 0)
        bucket["total_extra_cost_ms"] += float(row.total_extra_cost_ms or 0.0)

    for bucket in metrics.values():
        n = bucket["total"] or 1
        bucket["mean_extra_queries"] = bucket["total_extra_queries"] / n
        bucket["mean_extra_cost_ms"] = bucket["total_extra_cost_ms"] / n

    return metrics
