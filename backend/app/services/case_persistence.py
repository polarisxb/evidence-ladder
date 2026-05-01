"""Case persistence layer.

Responsible for writing a completed case_attempt dict to the database:
- AttackResult  (legacy compatibility)
- AttackCase
- AttackCaseVariant[]

Extracted from scan_runner.py to give persistence a clear, independently
testable module boundary.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AttackCase, AttackCaseVariant, AttackResult
from app.services.case_executor import build_attack_case_summary_json
from app.services.case_serializer import derive_judge_fields
from app.services.control_variants import CONTROL_VARIANT_VERSION
from app.services.risk_scorer import compute_risk_score


def build_judge_fields(case_summary: dict, analysis, case_attempt: dict) -> dict:
    """Build judge_snapshot, review_required, reportable for AttackCase persistence."""
    raw = analysis.model_dump() if hasattr(analysis, "model_dump") else {}
    snapshot, review_required, reportable = derive_judge_fields(
        verdict_status=case_summary.get("verdict_status"),
        verdict_reason=case_summary.get("verdict_reason"),
        execution_mode=raw.get("execution_mode"),
        blackbox_outcome=raw.get("blackbox_outcome"),
        control_assessment=case_summary.get("control_assessment"),
        attack_goal_score=raw.get("attack_goal_score"),
        utility_score=raw.get("utility_score"),
        business_verification_status=case_attempt.get("business_verification_status"),
        judge_version=settings.judge_version or None,
    )
    return {"judge_snapshot": snapshot, "review_required": review_required, "reportable": reportable}


def build_attack_result_analysis_raw(case_attempt: dict, extra_raw: dict | None = None) -> dict:
    analysis_raw = {
        **case_attempt["analysis"].model_dump(),
        **case_attempt["verdict"],
        "control_variant_version": CONTROL_VARIANT_VERSION if case_attempt["control_results"] else None,
        "control_variants": case_attempt["control_results"],
        **case_attempt["control_summary"],
        "case_summary": case_attempt["case_summary"],
        "response_evaluation": case_attempt.get("response_evaluation"),
        "business_verification_status": case_attempt.get("business_verification_status"),
        "probe_summary": case_attempt.get("probe_summary"),
    }
    if extra_raw:
        analysis_raw.update(extra_raw)
    return analysis_raw


def _resolved_rule_verified_risk_score(case_attempt: dict, risk_level: str) -> float:
    existing_score = float(case_attempt.get("risk_score") or 0.0)
    if existing_score > 0:
        return existing_score

    analysis = case_attempt["analysis"]
    recomputed = compute_risk_score(
        analysis.model_copy(update={"attack_successful": True, "risk_level": risk_level})
    )
    if recomputed > 0:
        return float(recomputed)

    return 7.0 if risk_level in {"high", "critical"} else 5.0


async def persist_case_with_legacy_result(
    db: AsyncSession,
    task,
    template: dict,
    case_attempt: dict,
    *,
    record_template_id: str | None = None,
    record_attack_name: str | None = None,
    record_technique: str | None = None,
    legacy_payload_text: str | None = None,
    legacy_analysis_extra: dict | None = None,
    auto_commit: bool = True,
) -> tuple[AttackCase, AttackResult]:
    analysis = case_attempt["analysis"]
    template_id = record_template_id or template["id"]
    attack_name = record_attack_name or template["name"]
    technique = record_technique or template.get("technique", "")

    verdict_status = (case_attempt.get("verdict") or {}).get("verdict_status") or ""
    rule_verified = verdict_status == "rule_verified"
    legacy_risk_level = (
        analysis.risk_level
        if (analysis.risk_level and analysis.risk_level != "none")
        else ("high" if rule_verified else analysis.risk_level)
    )
    legacy_risk_score = (
        _resolved_rule_verified_risk_score(case_attempt, legacy_risk_level)
        if rule_verified
        else float(case_attempt["risk_score"])
    )

    try:
        legacy_result = AttackResult(
            scan_task_id=task.id,
            template_id=template_id,
            category=template.get("category", ""),
            technique=technique,
            attack_name=attack_name,
            payload_text=legacy_payload_text or case_attempt["payload_text"],
            target_response=case_attempt["target_response"],
            attack_successful=True if rule_verified else analysis.attack_successful,
            confidence=max(analysis.confidence, 0.9) if rule_verified else analysis.confidence,
            risk_level=legacy_risk_level,
            evidence=analysis.evidence,
            leaked_info=analysis.leaked_info,
            explanation=analysis.explanation,
            remediation=analysis.remediation,
            owasp_id=template.get("owasp_id", ""),
            risk_score=legacy_risk_score,
            analysis_raw=build_attack_result_analysis_raw(case_attempt, legacy_analysis_extra),
        )
        db.add(legacy_result)
        await db.flush()

        case_summary = build_attack_case_summary_json(case_attempt["case_summary"])
        attack_case = AttackCase(
            id=case_attempt["case_id"],
            scan_task_id=task.id,
            template_id=template_id,
            category=template.get("category", ""),
            technique=technique,
            attack_name=attack_name,
            protocol_version=CONTROL_VARIANT_VERSION,
            case_status="completed",
            case_final_outcome=case_summary["case_final_outcome"],
            attack_variant_response=case_attempt["target_response"],
            control_assessment=case_summary["control_assessment"],
            control_summary=case_summary["control_summary"],
            verdict_status=case_summary["verdict_status"],
            verdict_reason=case_summary["verdict_reason"],
            business_verification_status=case_attempt.get("business_verification_status"),
            probe_summary=case_attempt.get("probe_summary"),
            probe_evidence_json=case_attempt.get("probe_evidence_json"),
            legacy_attack_result_id=legacy_result.id,
            summary_json=case_summary,
            **build_judge_fields(case_summary, analysis, case_attempt),
        )
        db.add(attack_case)
        await db.flush()

        db.add_all(
            [
                AttackCaseVariant(
                    attack_case_id=attack_case.id,
                    variant_type=str(case_variant.get("variant_type", "unknown")),
                    position=int(case_variant.get("position", 0) or 0),
                    request_text=str(case_variant.get("request_text", "")),
                    response_text=case_variant.get("response_text"),
                    response_error=case_variant.get("response_error"),
                    response_status=case_variant.get("response_status"),
                    latency_ms=(
                        float(case_variant["latency_ms"])
                        if isinstance(case_variant.get("latency_ms"), (int, float))
                        else None
                    ),
                    analysis_raw=(
                        dict(case_variant.get("analysis_raw") or {})
                        if isinstance(case_variant.get("analysis_raw") or {}, dict)
                        else None
                    ),
                    is_primary=bool(case_variant.get("is_primary", False)),
                    started_at=case_variant.get("started_at"),
                    completed_at=case_variant.get("completed_at"),
                )
                for case_variant in case_attempt["case_variants"]
            ]
        )
        if auto_commit:
            await db.commit()
        return attack_case, legacy_result
    except Exception:
        if auto_commit:
            await db.rollback()
        raise
