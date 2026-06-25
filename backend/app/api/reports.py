import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.models import ScanTask, AttackCase, AttackResult
from app.schemas.scan import AttackResultResponse, AttackResultReviewRequest
from app.schemas.report import AnalysisResult, CvssMetrics
from app.services.concealment_detector import detect_concealment
from app.services.report_generator import generate_report, render_html_report
from app.services.risk_scorer import compute_posture_metrics, compute_risk_score
from app.services.case_serializer import derive_judge_fields
from app.services.response_screening import extract_response_evaluation, is_not_evaluable_response
from app.services.response_screening import infer_not_evaluable_response_evaluation
from app.services.scan_recovery import finalize_stuck_scan_from_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _entry_text(entry, field: str) -> str:
    value = entry.get(field) if isinstance(entry, dict) else getattr(entry, field, None)
    return value if isinstance(value, str) and value.strip() else ""


def _last_non_empty(entries: list | None, field: str) -> str:
    if not entries:
        return ""
    for entry in reversed(entries):
        value = _entry_text(entry, field)
        if value:
            return value
    return ""


def _resolved_target_response(result: AttackResult, raw: dict) -> str | None:
    if isinstance(result.target_response, str) and result.target_response.strip():
        return result.target_response

    for key in ("crescendo_turns_detail", "pair_attempts", "iris_rounds", "tap_all_attempts"):
        response = _last_non_empty(raw.get(key), "response")
        if response:
            return response
    return result.target_response


def _resolved_verdict_status(result: AttackResult, raw: dict) -> str:
    verdict_status = raw.get("verdict_status")
    if isinstance(verdict_status, str) and verdict_status:
        return verdict_status
    if is_not_evaluable_response(raw):
        return "not_evaluable"
    target_response = _resolved_target_response(result, raw) or ""
    if target_response.strip().lower().startswith("[error]") or target_response.strip().lower().startswith("error:"):
        return "not_evaluable"
    return "manual_review_needed" if result.attack_successful else "passed"


def _resolved_execution_mode(raw: dict) -> str | None:
    value = raw.get("execution_mode")
    return value if isinstance(value, str) and value else None


def _resolved_blackbox_outcome(raw: dict) -> str | None:
    value = raw.get("blackbox_outcome")
    return value if isinstance(value, str) and value else None


def _resolved_behavior_flags(raw: dict) -> dict[str, bool | None]:
    value = raw.get("behavior_flags")
    return value if isinstance(value, dict) else {}


def _resolved_optional_float(raw: dict, key: str) -> float | None:
    value = raw.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _resolved_optional_string(raw: dict, key: str) -> str | None:
    value = raw.get(key)
    return value if isinstance(value, str) and value else None


def _resolved_control_assessment(raw: dict) -> str | None:
    return _resolved_optional_string(raw, "control_assessment")


def _resolved_control_summary(raw: dict) -> str | None:
    return _resolved_optional_string(raw, "control_summary")


def _loaded_attack_case(result: AttackResult):
    return result.__dict__.get("attack_case")


def _resolved_case_summary(result: AttackResult, raw: dict) -> dict:
    attack_case = _loaded_attack_case(result)
    if attack_case and isinstance(attack_case.summary_json, dict):
        return attack_case.summary_json
    case_summary = raw.get("case_summary")
    return case_summary if isinstance(case_summary, dict) else {}


def _resolved_case_id(result: AttackResult) -> str | None:
    attack_case = _loaded_attack_case(result)
    return attack_case.id if attack_case else None


def _resolved_case_final_outcome(result: AttackResult, raw: dict) -> str | None:
    attack_case = _loaded_attack_case(result)
    if attack_case and isinstance(attack_case.case_final_outcome, str) and attack_case.case_final_outcome:
        return attack_case.case_final_outcome
    case_summary = _resolved_case_summary(result, raw)
    value = case_summary.get("case_final_outcome")
    return value if isinstance(value, str) and value else None


def _resolved_quartet_present(result: AttackResult, raw: dict) -> bool | None:
    case_summary = _resolved_case_summary(result, raw)
    value = case_summary.get("quartet_present")
    return value if isinstance(value, bool) else None


def _resolved_business_verification_status(result: AttackResult, raw: dict) -> str:
    attack_case = _loaded_attack_case(result)
    if attack_case and isinstance(attack_case.business_verification_status, str) and attack_case.business_verification_status:
        return attack_case.business_verification_status

    case_summary = _resolved_case_summary(result, raw)
    value = case_summary.get("business_verification_status")
    if isinstance(value, str) and value:
        return value

    value = raw.get("business_verification_status")
    if isinstance(value, str) and value:
        return value

    behavior_flags = raw.get("behavior_flags")
    if isinstance(behavior_flags, dict) and behavior_flags.get("unauthorized_action_claim") is True:
        return "text_claim_only"
    return "not_applicable"


def _resolved_probe_summary(result: AttackResult, raw: dict, status: str) -> dict:
    attack_case = _loaded_attack_case(result)
    if attack_case and isinstance(attack_case.probe_summary, dict):
        return attack_case.probe_summary

    case_summary = _resolved_case_summary(result, raw)
    value = case_summary.get("probe_summary")
    if isinstance(value, dict):
        return value

    value = raw.get("probe_summary")
    if isinstance(value, dict):
        return value

    return {
        "status": status,
        "failure_type": None,
        "failure_reason": None,
        "verified_assertion_count": 0,
        "total_assertion_count": 0,
        "step_count": 0,
    }


def _resolved_probe_evidence_preview(result: AttackResult, raw: dict) -> list[dict]:
    attack_case = _loaded_attack_case(result)
    probe_evidence = (
        attack_case.probe_evidence_json
        if attack_case and isinstance(attack_case.probe_evidence_json, dict)
        else raw.get("probe_evidence_json")
    )
    if not isinstance(probe_evidence, dict):
        return []
    evidence = probe_evidence.get("evidence")
    if not isinstance(evidence, list):
        return []
    preview: list[dict] = []
    for entry in evidence:
        if isinstance(entry, dict):
            preview.append(entry)
        if len(preview) >= 3:
            break
    return preview


def _resolved_concealment(raw: dict, verdict_status: str, business_verification_status: str):
    return detect_concealment({
        "verdict_status": verdict_status,
        "blackbox_outcome": raw.get("blackbox_outcome"),
        "business_verification_status": business_verification_status,
        "behavior_flags": raw.get("behavior_flags", {}),
        "rule_hits": raw.get("rule_hits", []),
        "tool_calls": raw.get("tool_calls"),
    })


def _serialize_attack_result(result) -> AttackResultResponse:
    raw = result.analysis_raw or {}
    verdict_status = _resolved_verdict_status(result, raw)
    target_response = _resolved_target_response(result, raw)
    business_verification_status = _resolved_business_verification_status(result, raw)
    concealment = _resolved_concealment(raw, verdict_status, business_verification_status)
    response_evaluation = extract_response_evaluation(raw) or infer_not_evaluable_response_evaluation(
        response_text=target_response,
        target_type="unknown",
    )
    return AttackResultResponse(
        id=result.id,
        template_id=result.template_id,
        category=result.category,
        technique=result.technique,
        attack_name=result.attack_name,
        payload_text=result.payload_text,
        target_response=target_response,
        attack_successful=result.attack_successful,
        confidence=result.confidence,
        risk_level=result.risk_level,
        evidence=result.evidence,
        leaked_info=result.leaked_info,
        explanation=result.explanation,
        remediation=result.remediation,
        owasp_id=result.owasp_id,
        risk_score=result.risk_score,
        verdict_status=verdict_status,
        verdict_reason=raw.get("verdict_reason"),
        rule_hits=raw.get("rule_hits", []) or [],
        execution_mode=_resolved_execution_mode(raw),
        blackbox_outcome=_resolved_blackbox_outcome(raw),
        behavior_flags=_resolved_behavior_flags(raw),
        attack_goal_score=_resolved_optional_float(raw, "attack_goal_score"),
        utility_score=_resolved_optional_float(raw, "utility_score"),
        utility_explanation=_resolved_optional_string(raw, "utility_explanation"),
        control_assessment=_resolved_control_assessment(raw),
        control_summary=_resolved_control_summary(raw),
        case_id=_resolved_case_id(result),
        case_final_outcome=_resolved_case_final_outcome(result, raw),
        quartet_present=_resolved_quartet_present(result, raw),
        business_verification_status=business_verification_status,
        probe_summary=_resolved_probe_summary(result, raw, business_verification_status),
        probe_evidence_preview=_resolved_probe_evidence_preview(result, raw),
        concealment_class=concealment.concealment_class,
        is_concealed=concealment.is_concealed,
        response_evaluation=response_evaluation,
        analysis_raw=raw,
        created_at=result.created_at,
    )


def _restore_original_snapshot(result: AttackResult, raw: dict, original: dict) -> None:
    result.attack_successful = bool(original.get("attack_successful", result.attack_successful))
    result.risk_level = str(original.get("risk_level", result.risk_level))
    result.risk_score = float(original.get("risk_score", result.risk_score))
    raw["verdict_status"] = original.get("verdict_status")
    raw["verdict_reason"] = original.get("verdict_reason")
    raw["rule_hits"] = original.get("rule_hits", [])


def _build_manual_verified_risk(raw: dict, result: AttackResult) -> tuple[str, float]:
    raw_risk_level = raw.get("risk_level")
    risk_level = raw_risk_level if raw_risk_level and raw_risk_level != "none" else "medium"

    cvss_raw = raw.get("cvss_metrics")
    cvss_metrics = CvssMetrics(**cvss_raw) if cvss_raw else None
    confidence = raw.get("confidence", result.confidence or 0.8)

    analysis = AnalysisResult(
        attack_successful=True,
        confidence=max(float(confidence), 0.7),
        risk_level=str(risk_level),
        evidence=raw.get("evidence") or result.evidence or "Manually verified finding.",
        leaked_info=raw.get("leaked_info") or result.leaked_info,
        explanation=raw.get("explanation") or result.explanation or "Manually verified by reviewer.",
        remediation=raw.get("remediation") or result.remediation,
        cvss_metrics=cvss_metrics,
    )
    score = compute_risk_score(analysis)
    if score <= 0:
        score = 5.0
    return str(risk_level), float(score)


def _sync_attack_case_review_state(
    attack_case: AttackCase,
    attack_result: AttackResult,
    raw: dict,
) -> None:
    summary_json = attack_case.summary_json if isinstance(attack_case.summary_json, dict) else {}
    summary_json = dict(summary_json)

    attack_case.verdict_status = raw.get("verdict_status")
    attack_case.verdict_reason = raw.get("verdict_reason")
    summary_json["verdict_status"] = raw.get("verdict_status")
    summary_json["verdict_reason"] = raw.get("verdict_reason")
    summary_json["primary_attack_successful"] = attack_result.attack_successful
    attack_case.summary_json = summary_json

    judge_version = None
    if isinstance(attack_case.judge_snapshot, dict):
        judge_version = attack_case.judge_snapshot.get("judge_version")

    attack_goal_score = _resolved_optional_float(raw, "attack_goal_score")
    utility_score = _resolved_optional_float(raw, "utility_score")
    snapshot, review_required, reportable = derive_judge_fields(
        verdict_status=raw.get("verdict_status"),
        verdict_reason=raw.get("verdict_reason"),
        execution_mode=_resolved_execution_mode(raw),
        blackbox_outcome=_resolved_blackbox_outcome(raw),
        control_assessment=attack_case.control_assessment or summary_json.get("control_assessment"),
        attack_goal_score=attack_goal_score,
        utility_score=utility_score,
        business_verification_status=(
            attack_case.business_verification_status
            or summary_json.get("business_verification_status")
        ),
        judge_version=judge_version if isinstance(judge_version, str) else None,
    )
    attack_case.judge_snapshot = snapshot
    attack_case.review_required = review_required
    attack_case.reportable = reportable


async def _refresh_scan_rollups(db: AsyncSession, scan_task_id: str) -> None:
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_task_id).options(selectinload(ScanTask.results))
    )
    task = result.scalar_one_or_none()
    if not task:
        return

    results_data = [
        {
            "attack_successful": row.attack_successful,
            "risk_score": row.risk_score,
            "verdict_status": _resolved_verdict_status(row, row.analysis_raw or {}),
            "response_evaluation": extract_response_evaluation(row.analysis_raw or {}),
            "target_response": _resolved_target_response(row, row.analysis_raw or {}),
        }
        for row in task.results
    ]
    posture = compute_posture_metrics(results_data)
    # Align with the single source of truth in ``finding_classifier``: only
    # confirmed + suspected cases count as vulnerabilities. Previously this
    # used ``successful_attacks`` which silently included
    # ``manual_review_needed`` cases and drifted away from the count written
    # by ``scan_runner`` / ``scan_recovery``.
    task.vulnerabilities_found = int(posture["confirmed_findings"])
    task.overall_score = float(posture["security_posture_score"])


@router.post("/{scan_id}/finalize-stuck", response_model=dict)
async def finalize_stuck_scan_via_reports(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Same as `POST /scans/{id}/finalize-stuck` — alternate path if scans routing is cached on an old proxy."""
    data = await finalize_stuck_scan_from_db(scan_id, db)
    return {"data": data, "message": "Scan marked completed from saved results"}


async def _load_completed_scan(scan_id: str, db: AsyncSession) -> ScanTask:
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_id).options(
            selectinload(ScanTask.results).selectinload(AttackResult.attack_case)
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan not found")
    if task.status in {"failed", "cancelled"}:
        if not task.results:
            raise AppException(400, "Scan has not produced results yet")
        return task
    if task.status != "completed":
        raise AppException(400, "Scan has not completed yet")
    return task


@router.get("/{scan_id}", response_model=dict)
async def get_report(scan_id: str, db: AsyncSession = Depends(get_db)):
    task = await _load_completed_scan(scan_id, db)
    report = generate_report(task)
    return {"data": report.model_dump(), "message": "ok"}


@router.get("/{scan_id}/export/json")
async def export_report_json(scan_id: str, db: AsyncSession = Depends(get_db)):
    task = await _load_completed_scan(scan_id, db)
    report = generate_report(task)
    filename = f"security-report-{scan_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    content = json.dumps(report.model_dump(), indent=2, ensure_ascii=False, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scan_id}/export/html")
async def export_report_html(scan_id: str, db: AsyncSession = Depends(get_db)):
    task = await _load_completed_scan(scan_id, db)
    report = generate_report(task)
    html = render_html_report(report)
    filename = f"security-report-{scan_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.html"
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scan_id}/results", response_model=dict)
async def get_attack_results(
    scan_id: str,
    category: str | None = None,
    successful_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_id).options(
            selectinload(ScanTask.results).selectinload(AttackResult.attack_case)
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan not found")

    results = task.results
    if category:
        results = [r for r in results if r.category == category]
    if successful_only:
        results = [r for r in results if r.attack_successful]

    return {
        "data": [_serialize_attack_result(r) for r in results],
        "message": "ok",
    }


@router.post("/results/{result_id}/review", response_model=dict)
async def review_attack_result(
    result_id: str,
    body: AttackResultReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AttackResult).where(AttackResult.id == result_id))
    attack_result = result.scalar_one_or_none()
    if not attack_result:
        raise AppException(404, "Attack result not found")
    attack_case_result = await db.execute(
        select(AttackCase).where(AttackCase.legacy_attack_result_id == result_id)
    )
    attack_case = attack_case_result.scalar_one_or_none()

    raw = dict(attack_result.analysis_raw or {})
    review_state = dict(raw.get("review_state") or {})
    original = review_state.get("original_snapshot")

    if body.verdict_status != "reset" and not original:
        review_state["original_snapshot"] = {
            "attack_successful": attack_result.attack_successful,
            "risk_level": attack_result.risk_level,
            "risk_score": attack_result.risk_score,
            "verdict_status": raw.get("verdict_status"),
            "verdict_reason": raw.get("verdict_reason"),
            "rule_hits": raw.get("rule_hits", []),
        }
        original = review_state["original_snapshot"]

    note = (body.review_note or "").strip()

    if body.verdict_status == "false_positive":
        attack_result.attack_successful = False
        attack_result.risk_level = "none"
        attack_result.risk_score = 0.0
        raw["verdict_status"] = "false_positive"
        raw["verdict_reason"] = note or "Manually marked as false positive."
        raw["rule_hits"] = []
    elif body.verdict_status == "manual_verified":
        risk_level, risk_score = _build_manual_verified_risk(raw, attack_result)
        attack_result.attack_successful = True
        attack_result.risk_level = risk_level
        attack_result.risk_score = risk_score
        raw["verdict_status"] = "manual_verified"
        raw["verdict_reason"] = note or "Manually verified by reviewer."
    else:
        if not original:
            raise AppException(400, "No manual review snapshot found to reset")
        _restore_original_snapshot(attack_result, raw, original)
        note = note or "Manual review reset to automatic verdict."

    raw["review_state"] = review_state
    raw["manual_review"] = {
        "action": body.verdict_status,
        "note": note,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    attack_result.analysis_raw = raw
    if attack_case is not None:
        _sync_attack_case_review_state(attack_case, attack_result, raw)
    await _refresh_scan_rollups(db, attack_result.scan_task_id)
    await db.commit()
    await db.refresh(attack_result)

    return {
        "data": _serialize_attack_result(attack_result),
        "message": "Attack result review updated",
    }
