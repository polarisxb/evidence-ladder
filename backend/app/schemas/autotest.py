from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.scan import ScanCreate, TargetConfig


AutoTestBudget = Literal["small", "medium", "full"]
AutoTestTargetType = Literal[
    "openai_compatible",
    "custom",
    "builtin_vulnerable",
    "adapter",
    "claude",
]


class AutoTestPlanRequest(BaseModel):
    name: str | None = None
    target_type: AutoTestTargetType = "openai_compatible"
    target_url: str = ""
    adapter_id: str | None = None
    target_config: TargetConfig | None = None
    runtime_vars: dict[str, Any] | None = None
    attack_categories: list[str] = Field(default_factory=lambda: ["all"])
    budget: AutoTestBudget = "medium"
    enable_quartet: bool = True
    enable_canary: bool = True
    enable_probe: bool = False
    max_retest_rounds: int | None = Field(None, ge=0, le=5)
    adapter: dict[str, Any] | None = None
    adapter_payload: dict[str, Any] | None = None
    probe_config: dict[str, Any] | None = None
    judge_provider_id: str | None = None
    judge_model: str | None = None
    generation_provider_id: str | None = None
    generation_model: str | None = None


class AutoTestPlanResponse(BaseModel):
    target_type: str
    budget: AutoTestBudget
    risk_categories: list[str]
    strategies: list[str]
    phases: list[str]
    probe_available: bool
    max_retest_rounds: int


class AutoTestDraftRequest(AutoTestPlanRequest):
    @model_validator(mode="after")
    def validate_scan_target(self):
        if self.target_type == "adapter" and not (self.adapter_id or "").strip():
            raise ValueError("adapter_id is required when target_type=adapter")
        if self.target_type == "custom" and not self.target_url.strip():
            raise ValueError("target_url is required when target_type=custom")
        return self


class AutoTestDraftResponse(BaseModel):
    plan: AutoTestPlanResponse
    scan_config: ScanCreate


class AutoTestSummaryItem(BaseModel):
    result_id: str
    category: str
    attack_name: str
    verdict_status: str | None = None
    business_verification_status: str | None = None
    evidence_level: str | None
    evidence_label: str
    is_evaluable: bool
    is_strong_evidence: bool
    needs_retest: bool
    conflict_types: list[str]
    not_evaluable_reason: str | None = None
    evidence_sources: list[str]
    concealment_class: str = "not_applicable"
    is_concealed: bool = False


class AutoTestRetestActionGroup(BaseModel):
    result_id: str
    category: str
    attack_name: str
    actions: list[dict[str, str]]


AutoTestRetestOutcome = Literal[
    "confirmed_by_retest",
    "overturned_by_retest",
    "manual_review_needed",
]


class AutoTestRetestSource(BaseModel):
    source_scan_id: str
    source_result_ids: list[str]
    retest_reason: str
    retest_type: str | None = None


class AutoTestRetestComparison(BaseModel):
    source_result_id: str
    source_category: str
    source_attack_name: str
    source_evidence_level: str | None
    source_conflict_types: list[str]
    matching_retest_result_ids: list[str]
    retest_evidence_levels: list[str]
    outcome: AutoTestRetestOutcome
    outcome_reason: str


class AutoTestRetestRunRecord(BaseModel):
    id: str
    source_scan_id: str
    retest_scan_id: str
    source_result_ids: list[str]
    retest_reason: str
    retest_type: str
    status: str
    outcome_counts: dict[str, int]
    comparison_snapshot: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutoTestSummaryResponse(BaseModel):
    scan_id: str
    scan_name: str
    scan_status: str
    metrics: dict[str, Any]
    items: list[AutoTestSummaryItem]
    retest_actions: list[AutoTestRetestActionGroup]
    retest_source: AutoTestRetestSource | None = None
    retest_comparisons: list[AutoTestRetestComparison] = Field(default_factory=list)
    retest_outcome_counts: dict[str, int] = Field(default_factory=dict)
    retest_run: AutoTestRetestRunRecord | None = None


class AutoTestRetestDraftResponse(BaseModel):
    source_scan_id: str
    source_result_ids: list[str]
    retest_reason: str
    action_count: int
    scan_config: ScanCreate
