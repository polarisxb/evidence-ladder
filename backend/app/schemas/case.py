from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from app.schemas.response_evaluation import ResponseEvaluationResponse


AttackCaseVariantType = Literal[
    "attack",
    "clean",
    "quoted_attack",
    "benign_distractor",
]
BusinessVerificationStatus = Literal[
    "not_applicable",
    "text_claim_only",
    "probe_verified",
    "probe_failed",
    "probe_inconclusive",
]


class AttackCaseVariantResponse(BaseModel):
    id: str
    variant_type: AttackCaseVariantType | str
    position: int
    request_text: str
    response_text: str | None
    response_error: str | None
    response_status: str | None
    latency_ms: float | None
    response_evaluation: ResponseEvaluationResponse | None = None
    analysis_raw: dict | None = None
    is_primary: bool
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttackCaseLegacyResultSummary(BaseModel):
    id: str
    attack_successful: bool
    confidence: float
    risk_level: str
    risk_score: float
    target_response: str | None
    verdict_status: str | None = None
    verdict_reason: str | None = None
    response_evaluation: ResponseEvaluationResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttackCaseListItem(BaseModel):
    id: str
    scan_task_id: str
    template_id: str
    category: str
    technique: str
    attack_name: str
    protocol_version: str
    case_status: str
    case_final_outcome: str | None
    attack_variant_response: str | None
    control_assessment: str | None
    control_summary: str | None
    verdict_status: str | None
    verdict_reason: str | None
    legacy_attack_result_id: str | None
    primary_attack_successful: bool | None = None
    quartet_present: bool = False
    variant_count: int = 0
    business_verification_status: BusinessVerificationStatus | str | None = None
    probe_summary: dict | None = None
    probe_evidence_preview: list[dict] = Field(default_factory=list)
    response_evaluation: ResponseEvaluationResponse | None = None
    summary_json: dict | None = None
    # Phase 4: judge calibration
    judge_snapshot: dict | None = None
    review_required: bool | None = None
    reportable: bool | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttackCaseDetailResponse(AttackCaseListItem):
    variants: list[AttackCaseVariantResponse] = Field(default_factory=list)
    legacy_result: AttackCaseLegacyResultSummary | None = None
    probe_evidence_json: dict | None = None
