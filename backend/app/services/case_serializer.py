from __future__ import annotations

from collections.abc import Iterable

from app.models import AttackCase, AttackCaseVariant, AttackResult
from app.schemas.case import (
    AttackCaseDetailResponse,
    AttackCaseLegacyResultSummary,
    AttackCaseListItem,
    AttackCaseVariantResponse,
)
from app.services.control_variants import CONTROL_VARIANT_VERSION
from app.services.response_screening import (
    extract_response_evaluation,
    infer_not_evaluable_response_evaluation,
    is_not_evaluable_response,
    response_evaluation_payload,
)


_EXPECTED_QUARTET_VARIANTS = {
    "attack",
    "clean",
    "quoted_attack",
    "benign_distractor",
}
_FALLBACK_VARIANT_ORDER = {
    "attack": 0,
    "clean": 1,
    "quoted_attack": 2,
    "benign_distractor": 3,
}


def serialize_attack_cases(cases: Iterable[AttackCase]) -> list[AttackCaseListItem]:
    return [serialize_attack_case(attack_case) for attack_case in cases]


def serialize_attack_case(attack_case: AttackCase) -> AttackCaseListItem:
    variants = _sorted_variants(attack_case)
    summary = _summary_json(attack_case)
    legacy_result = attack_case.legacy_attack_result
    legacy_raw = _analysis_raw(legacy_result)
    business_verification_status = _resolved_business_verification_status(
        attack_case,
        summary,
        legacy_raw,
    )
    probe_summary = _resolved_probe_summary(
        attack_case,
        summary,
        legacy_raw,
        business_verification_status,
    )
    probe_evidence_json = _resolved_probe_evidence_json(attack_case, legacy_raw)

    return AttackCaseListItem(
        id=attack_case.id,
        scan_task_id=attack_case.scan_task_id,
        template_id=attack_case.template_id,
        category=attack_case.category,
        technique=attack_case.technique,
        attack_name=attack_case.attack_name,
        protocol_version=_coalesce_string(
            attack_case.protocol_version,
            summary.get("protocol_version"),
            CONTROL_VARIANT_VERSION,
        )
        or CONTROL_VARIANT_VERSION,
        case_status=attack_case.case_status,
        case_final_outcome=_coalesce_string(
            attack_case.case_final_outcome,
            summary.get("case_final_outcome"),
        ),
        attack_variant_response=_resolved_attack_variant_response(
            attack_case,
            variants,
            legacy_result,
        ),
        control_assessment=_coalesce_string(
            attack_case.control_assessment,
            summary.get("control_assessment"),
            legacy_raw.get("control_assessment"),
        ),
        control_summary=_coalesce_string(
            attack_case.control_summary,
            summary.get("control_summary"),
            legacy_raw.get("control_summary"),
        ),
        verdict_status=_coalesce_string(
            legacy_raw.get("verdict_status"),
            attack_case.verdict_status,
            summary.get("verdict_status"),
        ) or _resolved_legacy_verdict_status(legacy_result, legacy_raw),
        verdict_reason=_coalesce_string(
            legacy_raw.get("verdict_reason"),
            attack_case.verdict_reason,
            summary.get("verdict_reason"),
        ),
        legacy_attack_result_id=attack_case.legacy_attack_result_id
        or (legacy_result.id if legacy_result else None),
        primary_attack_successful=_resolved_primary_attack_successful(
            summary,
            variants,
            legacy_result,
        ),
        quartet_present=_quartet_present(summary, variants),
        variant_count=_resolved_variant_count(summary, variants),
        business_verification_status=business_verification_status,
        probe_summary=probe_summary,
        probe_evidence_preview=_probe_evidence_preview(probe_evidence_json),
        response_evaluation=_resolved_case_response_evaluation(
            attack_case.attack_variant_response,
            summary,
            legacy_raw,
        ),
        summary_json=summary or None,
        # Phase 4: judge calibration — read directly from model columns
        judge_snapshot=attack_case.judge_snapshot,
        review_required=attack_case.review_required,
        reportable=attack_case.reportable,
        created_at=attack_case.created_at,
        updated_at=attack_case.updated_at,
    )


def serialize_attack_case_detail(attack_case: AttackCase) -> AttackCaseDetailResponse:
    list_item = serialize_attack_case(attack_case)
    variants = _sorted_variants(attack_case)

    return AttackCaseDetailResponse(
        **list_item.model_dump(),
        variants=[_serialize_variant(variant) for variant in variants],
        legacy_result=_serialize_legacy_result(attack_case.legacy_attack_result),
        probe_evidence_json=_resolved_probe_evidence_json(
            attack_case,
            _analysis_raw(attack_case.legacy_attack_result),
        ),
    )


def _serialize_variant(variant: AttackCaseVariant) -> AttackCaseVariantResponse:
    analysis_raw = variant.analysis_raw if isinstance(variant.analysis_raw, dict) else {}
    return AttackCaseVariantResponse(
        id=variant.id,
        variant_type=variant.variant_type,
        position=variant.position,
        request_text=variant.request_text,
        response_text=variant.response_text,
        response_error=variant.response_error,
        response_status=variant.response_status,
        latency_ms=variant.latency_ms,
        response_evaluation=response_evaluation_payload(extract_response_evaluation(analysis_raw)),
        analysis_raw=analysis_raw or None,
        is_primary=variant.is_primary,
        started_at=variant.started_at,
        completed_at=variant.completed_at,
        created_at=variant.created_at,
    )


def _serialize_legacy_result(
    legacy_result: AttackResult | None,
) -> AttackCaseLegacyResultSummary | None:
    if legacy_result is None:
        return None

    raw = _analysis_raw(legacy_result)
    response_evaluation = response_evaluation_payload(extract_response_evaluation(raw)) or infer_not_evaluable_response_evaluation(
        response_text=_resolved_target_response(legacy_result, raw),
        target_type="unknown",
    )
    return AttackCaseLegacyResultSummary(
        id=legacy_result.id,
        attack_successful=legacy_result.attack_successful,
        confidence=legacy_result.confidence,
        risk_level=legacy_result.risk_level,
        risk_score=legacy_result.risk_score,
        target_response=_resolved_target_response(legacy_result, raw),
        verdict_status=_resolved_legacy_verdict_status(legacy_result, raw),
        verdict_reason=_coalesce_string(raw.get("verdict_reason")),
        response_evaluation=response_evaluation,
        created_at=legacy_result.created_at,
    )


def _sorted_variants(attack_case: AttackCase) -> list[AttackCaseVariant]:
    variants = list(attack_case.variants or [])
    return sorted(
        variants,
        key=lambda item: (
            item.position,
            _FALLBACK_VARIANT_ORDER.get(item.variant_type, 99),
            item.created_at,
        ),
    )


def _summary_json(attack_case: AttackCase) -> dict:
    return attack_case.summary_json if isinstance(attack_case.summary_json, dict) else {}


def _resolved_case_response_evaluation(
    attack_variant_response: str | None,
    summary: dict,
    legacy_raw: dict,
) -> dict | None:
    for source in (summary, legacy_raw):
        resolved = response_evaluation_payload(extract_response_evaluation(source))
        if resolved is not None:
            return resolved
    return infer_not_evaluable_response_evaluation(
        response_text=attack_variant_response,
        target_type="unknown",
    )


def _analysis_raw(legacy_result: AttackResult | None) -> dict:
    if legacy_result is None or not isinstance(legacy_result.analysis_raw, dict):
        return {}
    return legacy_result.analysis_raw


def _resolved_business_verification_status(
    attack_case: AttackCase,
    summary: dict,
    legacy_raw: dict,
) -> str:
    for value in (
        attack_case.business_verification_status,
        summary.get("business_verification_status"),
        legacy_raw.get("business_verification_status"),
    ):
        if isinstance(value, str) and value:
            return value

    behavior_flags = legacy_raw.get("behavior_flags")
    if isinstance(behavior_flags, dict) and behavior_flags.get("unauthorized_action_claim") is True:
        return "text_claim_only"
    return "not_applicable"


def _resolved_probe_summary(
    attack_case: AttackCase,
    summary: dict,
    legacy_raw: dict,
    business_verification_status: str,
) -> dict:
    for value in (
        attack_case.probe_summary,
        summary.get("probe_summary"),
        legacy_raw.get("probe_summary"),
    ):
        if isinstance(value, dict):
            return value
    return {
        "status": business_verification_status,
        "failure_type": None,
        "failure_reason": None,
        "verified_assertion_count": 0,
        "total_assertion_count": 0,
        "step_count": 0,
    }


def _resolved_probe_evidence_json(attack_case: AttackCase, legacy_raw: dict) -> dict | None:
    if isinstance(attack_case.probe_evidence_json, dict):
        return attack_case.probe_evidence_json
    raw_value = legacy_raw.get("probe_evidence_json")
    return raw_value if isinstance(raw_value, dict) else None


def _probe_evidence_preview(probe_evidence_json: dict | None) -> list[dict]:
    if not isinstance(probe_evidence_json, dict):
        return []
    evidence = probe_evidence_json.get("evidence")
    if not isinstance(evidence, list):
        return []
    preview: list[dict] = []
    for entry in evidence:
        if isinstance(entry, dict):
            preview.append(entry)
        if len(preview) >= 3:
            break
    return preview


def _quartet_present(summary: dict, variants: list[AttackCaseVariant]) -> bool:
    quartet_present = summary.get("quartet_present")
    if isinstance(quartet_present, bool):
        return quartet_present
    seen_variants = {variant.variant_type for variant in variants}
    return _EXPECTED_QUARTET_VARIANTS.issubset(seen_variants)


def _resolved_variant_count(summary: dict, variants: list[AttackCaseVariant]) -> int:
    variant_count = summary.get("variant_count")
    if isinstance(variant_count, int) and variant_count >= 0:
        return variant_count
    return len(variants)


def _resolved_primary_attack_successful(
    summary: dict,
    variants: list[AttackCaseVariant],
    legacy_result: AttackResult | None,
) -> bool | None:
    if legacy_result is not None:
        return legacy_result.attack_successful

    primary_attack_successful = summary.get("primary_attack_successful")
    if isinstance(primary_attack_successful, bool):
        return primary_attack_successful

    primary_variant = _primary_variant(variants)
    if primary_variant and isinstance(primary_variant.analysis_raw, dict):
        analysis_value = primary_variant.analysis_raw.get("attack_successful")
        if isinstance(analysis_value, bool):
            return analysis_value
    return None


def _resolved_attack_variant_response(
    attack_case: AttackCase,
    variants: list[AttackCaseVariant],
    legacy_result: AttackResult | None,
) -> str | None:
    response = _coalesce_string(attack_case.attack_variant_response)
    if response:
        return response

    primary_variant = _primary_variant(variants)
    if primary_variant:
        response = _coalesce_string(primary_variant.response_text)
        if response:
            return response

    if legacy_result is not None:
        return _resolved_target_response(legacy_result, _analysis_raw(legacy_result))
    return None


def _primary_variant(variants: list[AttackCaseVariant]) -> AttackCaseVariant | None:
    for variant in variants:
        if variant.is_primary:
            return variant
    for variant in variants:
        if variant.variant_type == "attack":
            return variant
    return variants[0] if variants else None


def _resolved_target_response(legacy_result: AttackResult, raw: dict) -> str | None:
    response = _coalesce_string(legacy_result.target_response)
    if response:
        return response

    for key in ("crescendo_turns_detail", "pair_attempts", "iris_rounds", "tap_all_attempts"):
        response = _last_non_empty(raw.get(key), "response")
        if response:
            return response
    return None


def _resolved_legacy_verdict_status(legacy_result: AttackResult, raw: dict) -> str | None:
    explicit = _coalesce_string(raw.get("verdict_status"))
    if explicit:
        return explicit
    if is_not_evaluable_response(raw):
        return "not_evaluable"

    response = _resolved_target_response(legacy_result, raw) or ""
    lowered = response.strip().lower()
    if lowered.startswith("[error]") or lowered.startswith("error:"):
        return "not_evaluable"
    return None


def _entry_text(entry, field: str) -> str | None:
    value = entry.get(field) if isinstance(entry, dict) else getattr(entry, field, None)
    return _coalesce_string(value)


def _last_non_empty(entries: list | None, field: str) -> str | None:
    if not entries:
        return None
    for entry in reversed(entries):
        value = _entry_text(entry, field)
        if value:
            return value
    return None


def _coalesce_string(*values) -> str | None:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


_REVIEW_REQUIRED_STATUSES = {"manual_review_needed", "ai_suspected"}
_REPORTABLE_STATUSES = {"rule_verified", "manual_verified", "ai_suspected"}


def build_judge_snapshot(
    verdict_status: str | None,
    verdict_reason: str | None,
    execution_mode: str | None,
    blackbox_outcome: str | None,
    control_assessment: str | None,
    attack_goal_score: float | None,
    utility_score: float | None,
    business_verification_status: str | None,
    *,
    judge_version: str | None = None,
) -> dict:
    """Assemble a stable judge snapshot from known case-level fields.

    judge_version identifies which judge configuration produced this snapshot,
    enabling calibration runs to compare across judge versions.
    """
    review_required = verdict_status in _REVIEW_REQUIRED_STATUSES
    reportable = verdict_status in _REPORTABLE_STATUSES
    snapshot: dict = {
        "verdict_status": verdict_status,
        "verdict_reason": verdict_reason,
        "execution_mode": execution_mode,
        "blackbox_outcome": blackbox_outcome,
        "control_assessment": control_assessment,
        "attack_goal_score": attack_goal_score,
        "utility_score": utility_score,
        "business_verification_status": business_verification_status,
        "review_required": review_required,
        "reportable": reportable,
    }
    if judge_version is not None:
        snapshot["judge_version"] = judge_version
    return snapshot


def derive_judge_fields(
    verdict_status: str | None,
    verdict_reason: str | None,
    execution_mode: str | None,
    blackbox_outcome: str | None,
    control_assessment: str | None,
    attack_goal_score: float | None,
    utility_score: float | None,
    business_verification_status: str | None,
    *,
    judge_version: str | None = None,
) -> tuple[dict, bool, bool]:
    """Return (judge_snapshot, review_required, reportable)."""
    snapshot = build_judge_snapshot(
        verdict_status=verdict_status,
        verdict_reason=verdict_reason,
        execution_mode=execution_mode,
        blackbox_outcome=blackbox_outcome,
        control_assessment=control_assessment,
        attack_goal_score=attack_goal_score,
        utility_score=utility_score,
        business_verification_status=business_verification_status,
        judge_version=judge_version,
    )
    return snapshot, snapshot["review_required"], snapshot["reportable"]
