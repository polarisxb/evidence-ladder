"""AutoTest summary projection from persisted scan results."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models import AttackResult, AutoTestRetestRun, ScanTask
from app.schemas.autotest import (
    AutoTestRetestActionGroup,
    AutoTestRetestComparison,
    AutoTestRetestRunRecord,
    AutoTestRetestSource,
    AutoTestSummaryItem,
    AutoTestSummaryResponse,
)
from app.services.autotest_metrics import compute_autotest_metrics
from app.services.autotest_retest_runs import get_retest_run_for_scan
from app.services.concealment_detector import detect_concealment
from app.services.evidence_arbiter import arbitrate_evidence
from app.services.retest_policy import RetestConfig, plan_retests


_RETEST_OUTCOMES = (
    "confirmed_by_retest",
    "overturned_by_retest",
    "manual_review_needed",
)
_CONFIRMING_CONTROL_ASSESSMENTS = {
    "attack_delta_supported",
    "rule_verified_finding",
}
_OVERTURNING_CONTROL_ASSESSMENTS = {
    "discussion_supported",
    "passed",
    "false_positive",
}
_INCONCLUSIVE_CONTROL_ASSESSMENTS = {
    "controls_inconclusive",
    "controls_missing",
}


async def build_autotest_summary(scan_id: str, db: AsyncSession) -> AutoTestSummaryResponse:
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_id).options(
            selectinload(ScanTask.results).selectinload(AttackResult.attack_case)
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise AppException(404, "Scan not found")

    result_payloads = [_result_payload(row) for row in task.results]
    metrics = compute_autotest_metrics(result_payloads)

    items: list[AutoTestSummaryItem] = []
    action_groups: list[AutoTestRetestActionGroup] = []
    retest_config = _retest_config_for_task(task)

    for payload in result_payloads:
        assessment = arbitrate_evidence(payload)
        concealment = detect_concealment(payload)
        actions = plan_retests(payload, retest_config)
        items.append(AutoTestSummaryItem(
            result_id=str(payload["id"]),
            category=str(payload.get("category") or ""),
            attack_name=str(payload.get("attack_name") or ""),
            verdict_status=_optional_str(payload.get("verdict_status")),
            business_verification_status=_optional_str(payload.get("business_verification_status")),
            evidence_level=assessment.evidence_level,
            evidence_label=assessment.evidence_label,
            is_evaluable=assessment.is_evaluable,
            is_strong_evidence=assessment.is_strong_evidence,
            needs_retest=assessment.needs_retest,
            conflict_types=list(assessment.conflict_types),
            not_evaluable_reason=assessment.not_evaluable_reason,
            evidence_sources=list(assessment.evidence_sources),
            concealment_class=concealment.concealment_class,
            is_concealed=concealment.is_concealed,
        ))
        if actions:
            action_groups.append(AutoTestRetestActionGroup(
                result_id=str(payload["id"]),
                category=str(payload.get("category") or ""),
                attack_name=str(payload.get("attack_name") or ""),
                actions=[action.to_dict() for action in actions],
            ))

    retest_run = await get_retest_run_for_scan(task.id, db)
    retest_source = _retest_source_for_run(retest_run) if retest_run is not None else _retest_source_for_task(task)
    retest_comparisons: list[AutoTestRetestComparison] = []
    if retest_source is not None:
        source_payloads = await _source_result_payloads(retest_source, db)
        retest_comparisons = _build_retest_comparisons(source_payloads, result_payloads)

    metrics_dict = metrics.to_dict()
    retest_outcome_counts = _retest_outcome_counts(retest_comparisons)
    if retest_outcome_counts:
        metrics_dict["overturned_count"] = retest_outcome_counts.get("overturned_by_retest", 0)

    if retest_run is not None:
        await _persist_retest_run_snapshot(retest_run, retest_comparisons, retest_outcome_counts, db)

    return AutoTestSummaryResponse(
        scan_id=task.id,
        scan_name=task.name,
        scan_status=task.status,
        metrics=metrics_dict,
        items=items,
        retest_actions=action_groups,
        retest_source=retest_source,
        retest_comparisons=retest_comparisons,
        retest_outcome_counts=retest_outcome_counts,
        retest_run=AutoTestRetestRunRecord.model_validate(retest_run) if retest_run is not None else None,
    )


def _result_payload(result: AttackResult) -> dict[str, Any]:
    raw = result.analysis_raw if isinstance(result.analysis_raw, dict) else {}
    attack_case = result.__dict__.get("attack_case")
    case_summary = (
        attack_case.summary_json
        if attack_case is not None and isinstance(attack_case.summary_json, dict)
        else raw.get("case_summary")
    )
    if not isinstance(case_summary, Mapping):
        case_summary = {}

    business_status = _first_str(
        getattr(attack_case, "business_verification_status", None) if attack_case is not None else None,
        case_summary.get("business_verification_status"),
        raw.get("business_verification_status"),
        "not_applicable",
    )

    response_evaluation = raw.get("response_evaluation")
    if not isinstance(response_evaluation, Mapping):
        response_evaluation = {}

    payload = {
        "id": result.id,
        "template_id": result.template_id,
        "category": result.category,
        "attack_name": result.attack_name,
        "variant_type": _first_str(
            raw.get("variant_type"),
            case_summary.get("variant_type"),
            "attack",
        ),
        "attack_successful": result.attack_successful,
        "confidence": result.confidence,
        "verdict_status": _first_str(
            raw.get("verdict_status"),
            getattr(attack_case, "verdict_status", None) if attack_case is not None else None,
            "ai_suspected" if result.attack_successful else "passed",
        ),
        "blackbox_outcome": raw.get("blackbox_outcome"),
        "rule_hits": raw.get("rule_hits") if isinstance(raw.get("rule_hits"), list) else [],
        "behavior_flags": raw.get("behavior_flags") if isinstance(raw.get("behavior_flags"), dict) else {},
        "control_assessment": _first_str(
            raw.get("control_assessment"),
            getattr(attack_case, "control_assessment", None) if attack_case is not None else None,
            case_summary.get("control_assessment"),
        ),
        "business_verification_status": business_status,
        "probe_summary": _probe_summary(attack_case, raw, case_summary),
        "response_evaluation": dict(response_evaluation),
        "quartet_validated": _quartet_validated(raw, case_summary),
        "extra_query_count": _extra_query_count(raw, case_summary),
    }
    return payload


def _retest_source_for_task(task: ScanTask) -> AutoTestRetestSource | None:
    runtime_vars = task.runtime_vars if isinstance(task.runtime_vars, Mapping) else {}
    namespaced = runtime_vars.get("autotest_retest")
    source_meta = namespaced if isinstance(namespaced, Mapping) else runtime_vars

    source_scan_id = _first_str(source_meta.get("source_scan_id"))
    if not source_scan_id:
        return None

    return AutoTestRetestSource(
        source_scan_id=source_scan_id,
        source_result_ids=_string_list(source_meta.get("source_result_ids")),
        retest_reason=_first_str(source_meta.get("retest_reason"), "unknown"),
        retest_type=_optional_str(source_meta.get("retest_type")),
    )


def _retest_source_for_run(run: AutoTestRetestRun) -> AutoTestRetestSource:
    return AutoTestRetestSource(
        source_scan_id=run.source_scan_id,
        source_result_ids=_string_list(run.source_result_ids),
        retest_reason=run.retest_reason,
        retest_type=run.retest_type,
    )


async def _persist_retest_run_snapshot(
    run: AutoTestRetestRun,
    comparisons: list[AutoTestRetestComparison],
    outcome_counts: dict[str, int],
    db: AsyncSession,
) -> None:
    run.outcome_counts = dict(outcome_counts)
    run.comparison_snapshot = [comparison.model_dump() for comparison in comparisons]
    run.status = "summarized"
    await db.commit()
    await db.refresh(run)


async def _source_result_payloads(
    retest_source: AutoTestRetestSource,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    if not retest_source.source_result_ids:
        return []

    result = await db.execute(
        select(AttackResult)
        .where(
            AttackResult.scan_task_id == retest_source.source_scan_id,
            AttackResult.id.in_(retest_source.source_result_ids),
        )
        .options(selectinload(AttackResult.attack_case))
    )
    rows = result.scalars().all()
    by_id = {row.id: row for row in rows}
    return [
        _result_payload(by_id[result_id])
        for result_id in retest_source.source_result_ids
        if result_id in by_id
    ]


def _build_retest_comparisons(
    source_payloads: list[dict[str, Any]],
    retest_payloads: list[dict[str, Any]],
) -> list[AutoTestRetestComparison]:
    comparisons: list[AutoTestRetestComparison] = []
    for source_payload in source_payloads:
        source_assessment = arbitrate_evidence(source_payload)
        matches = _matching_retest_payloads(source_payload, retest_payloads)
        retest_assessments = [arbitrate_evidence(payload) for payload in matches]
        outcome, reason = _classify_retest_outcome(matches, retest_assessments)
        comparisons.append(AutoTestRetestComparison(
            source_result_id=str(source_payload["id"]),
            source_category=str(source_payload.get("category") or ""),
            source_attack_name=str(source_payload.get("attack_name") or ""),
            source_evidence_level=source_assessment.evidence_level,
            source_conflict_types=list(source_assessment.conflict_types),
            matching_retest_result_ids=[str(payload["id"]) for payload in matches],
            retest_evidence_levels=[
                assessment.evidence_level or "none"
                for assessment in retest_assessments
            ],
            outcome=outcome,
            outcome_reason=reason,
        ))
    return comparisons


def _matching_retest_payloads(
    source_payload: Mapping[str, Any],
    retest_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_template = str(source_payload.get("template_id") or "").strip()
    source_category = str(source_payload.get("category") or "").strip()
    source_attack_name = str(source_payload.get("attack_name") or "").strip()

    exact = [
        payload
        for payload in retest_payloads
        if source_template
        and str(payload.get("template_id") or "").strip() == source_template
        and (not source_category or str(payload.get("category") or "").strip() == source_category)
    ]
    if exact:
        return exact

    category_and_name = [
        payload
        for payload in retest_payloads
        if source_category
        and source_attack_name
        and str(payload.get("category") or "").strip() == source_category
        and str(payload.get("attack_name") or "").strip() == source_attack_name
    ]
    if category_and_name:
        return category_and_name

    if source_category:
        return [
            payload
            for payload in retest_payloads
            if str(payload.get("category") or "").strip() == source_category
        ]
    return []


def _classify_retest_outcome(
    retest_payloads: list[dict[str, Any]],
    retest_assessments: list[Any],
) -> tuple[str, str]:
    if not retest_payloads:
        return "manual_review_needed", "no_matching_retest_result"

    if any(
        _is_confirming_retest(payload, assessment)
        for payload, assessment in zip(retest_payloads, retest_assessments, strict=True)
    ):
        return "confirmed_by_retest", "retest_found_strong_evidence"

    if any(not assessment.is_evaluable for assessment in retest_assessments):
        return "manual_review_needed", "retest_not_evaluable"

    if any(
        _is_inconclusive_retest(payload) or assessment.needs_retest
        for payload, assessment in zip(retest_payloads, retest_assessments, strict=True)
    ):
        return "manual_review_needed", "retest_remains_inconclusive"

    if any(assessment.evidence_level in {"E1", "E2"} for assessment in retest_assessments):
        return "manual_review_needed", "retest_evidence_still_weak"

    if all(
        _is_overturning_retest(payload, assessment)
        for payload, assessment in zip(retest_payloads, retest_assessments, strict=True)
    ):
        return "overturned_by_retest", "quartet_controls_did_not_reproduce_finding"

    return "manual_review_needed", "retest_outcome_unclassified"


def _is_confirming_retest(payload: Mapping[str, Any], assessment: Any) -> bool:
    if payload.get("quartet_validated") is True:
        return True
    if assessment.is_strong_evidence:
        return True
    return str(payload.get("control_assessment") or "").strip() in _CONFIRMING_CONTROL_ASSESSMENTS


def _is_overturning_retest(payload: Mapping[str, Any], assessment: Any) -> bool:
    control_assessment = str(payload.get("control_assessment") or "").strip()
    blackbox_outcome = str(payload.get("blackbox_outcome") or "").strip()
    verdict_status = str(payload.get("verdict_status") or "").strip()
    return (
        not assessment.is_strong_evidence
        and (
            control_assessment in _OVERTURNING_CONTROL_ASSESSMENTS
            or blackbox_outcome == "NO_INJECTION_SUCCESS"
            or verdict_status in {"passed", "false_positive"}
            or payload.get("attack_successful") is False
        )
    )


def _is_inconclusive_retest(payload: Mapping[str, Any]) -> bool:
    return str(payload.get("control_assessment") or "").strip() in _INCONCLUSIVE_CONTROL_ASSESSMENTS


def _retest_outcome_counts(comparisons: list[AutoTestRetestComparison]) -> dict[str, int]:
    if not comparisons:
        return {}
    counts = {outcome: 0 for outcome in _RETEST_OUTCOMES}
    for comparison in comparisons:
        counts[comparison.outcome] = counts.get(comparison.outcome, 0) + 1
    return counts


def _retest_config_for_task(task: ScanTask) -> RetestConfig:
    advanced = task.advanced_config if isinstance(task.advanced_config, dict) else {}
    quartet_mode = str(advanced.get("quartet_mode") or "adaptive")
    return RetestConfig(
        max_retest_rounds=int(advanced.get("max_retest_rounds") or 1),
        current_retest_round=int(advanced.get("current_retest_round") or 0),
        quartet_enabled=quartet_mode != "off",
        canary_enabled=True,
        probe_available=task.target_type == "adapter",
    )


def _probe_summary(attack_case: Any, raw: Mapping[str, Any], case_summary: Mapping[str, Any]) -> dict[str, Any]:
    if attack_case is not None and isinstance(getattr(attack_case, "probe_summary", None), dict):
        return dict(attack_case.probe_summary)
    if isinstance(case_summary.get("probe_summary"), dict):
        return dict(case_summary["probe_summary"])
    if isinstance(raw.get("probe_summary"), dict):
        return dict(raw["probe_summary"])
    return {}


def _quartet_validated(raw: Mapping[str, Any], case_summary: Mapping[str, Any]) -> bool:
    if raw.get("quartet_validated") is True:
        return True
    return case_summary.get("control_assessment") == "attack_delta_supported"


def _extra_query_count(raw: Mapping[str, Any], case_summary: Mapping[str, Any]) -> int:
    for value in (raw.get("extra_query_count"), case_summary.get("extra_query_count")):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def _first_str(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for text in (_optional_str(item) for item in value) if text]
    if isinstance(value, tuple):
        return [text for text in (_optional_str(item) for item in value) if text]
    text = _optional_str(value)
    return [text] if text else []
