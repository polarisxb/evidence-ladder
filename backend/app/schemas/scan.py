from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from app.schemas.response_evaluation import ResponseEvaluationResponse


BusinessVerificationStatus = Literal[
    "not_applicable",
    "text_claim_only",
    "probe_verified",
    "probe_failed",
    "probe_inconclusive",
]

TargetHealthStatus = Literal["healthy", "degraded", "unhealthy"]


class StructuredOriginRule(BaseModel):
    """JSON-path or header-based origin rule for structured response matching."""
    field: str                      # e.g. "$.guardrail.action" or "header:x-blocked"
    op: str = "eq"                  # eq / ne / exists / not_exists / contains
    value: Any = True
    mark: str = "blocked"           # blocked / model / post_processed
    reason: str | None = None       # block_reason or post_reason
    label: str | None = None        # human-readable description


class TargetOriginRules(BaseModel):
    exact: list[str] = Field(default_factory=list)
    contains: list[str] = Field(default_factory=list)
    regex: list[str] = Field(default_factory=list)
    structured: list[StructuredOriginRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_regex(self):
        for pattern in self.regex:
            if isinstance(pattern, str) and pattern.strip():
                re.compile(pattern)
        return self


class TargetConfig(BaseModel):
    # 关联已配置的供应商 ID，设置后自动使用该供应商的 API Key / Base URL / 模型
    provider_id: str | None = None
    api_key: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    canary_tokens: list[str] | None = None
    headers: dict[str, str] | None = None
    timeout_s: float | None = Field(None, gt=0, le=300)
    vulnerable_level: int | None = Field(None, ge=1, le=4)
    origin_rules: TargetOriginRules | None = None


class AdvancedConfig(BaseModel):
    enable_crescendo: bool = False
    enable_tap: bool = False
    enable_pair: bool = False
    enable_self_explanation: bool = False
    enable_mutations: bool = False
    # quartet_mode supersedes enable_control_variants.
    # full     — always run all 4 variants (default)
    # adaptive — run attack first; skip controls when clearly failed (confidence >= 0.85)
    # off      — only run attack variant
    quartet_mode: Literal["full", "adaptive", "off"] = "full"
    # Legacy field kept for backward compat — mapped to quartet_mode by validator below
    enable_control_variants: bool | None = None
    parallel_attacks: int = Field(3, ge=1, le=10)

    @model_validator(mode="after")
    def _map_legacy_control_variants(self):
        """If enable_control_variants was explicitly set but quartet_mode was not,
        map it for backward compatibility."""
        if self.enable_control_variants is not None:
            # Only override quartet_mode when it's still at the default value
            if self.quartet_mode == "full" and not self.enable_control_variants:
                self.quartet_mode = "off"
        return self
    enable_fitd: bool = False
    fitd_num_levels: int = Field(6, ge=3, le=12)
    enable_msj: bool = False
    msj_shot_count: int = Field(32, ge=8, le=128)
    enable_ice: bool = False
    crescendo_max_turns: int = Field(10, ge=3, le=20)
    tap_branching_factor: int = Field(4, ge=2, le=8)
    tap_max_depth: int = Field(10, ge=3, le=20)
    pair_max_rounds: int = Field(20, ge=3, le=20)
    self_explanation_rounds: int = Field(5, ge=2, le=10)
    mutation_strategies: list[str] = Field(default_factory=list)


class ScanCreate(BaseModel):
    name: str = "Untitled Scan"
    target_url: str = ""
    target_type: Literal["openai_compatible", "custom", "builtin_vulnerable", "adapter", "claude"] = "openai_compatible"
    adapter_id: str | None = None
    target_config: TargetConfig | None = None
    runtime_vars: dict[str, Any] | None = None
    attack_categories: list[str] = Field(default=["all"])
    advanced: AdvancedConfig | None = None
    judge_provider_id: str | None = None
    judge_model: str | None = None
    generation_provider_id: str | None = None
    generation_model: str | None = None

    @model_validator(mode="after")
    def validate_target_shape(self):
        if self.target_type == "adapter":
            if not (self.adapter_id or "").strip():
                raise ValueError("adapter_id is required when target_type=adapter")
            return self

        if self.adapter_id:
            raise ValueError("adapter_id is only allowed when target_type=adapter")
        if self.target_type == "custom" and not self.target_url.strip():
            raise ValueError("target_url is required when target_type=custom")
        return self


class ScanResponse(BaseModel):
    id: str
    name: str
    status: str
    target_url: str
    target_type: str
    adapter_id: str | None = None
    attack_categories: list[str]
    total_attacks: int
    completed_attacks: int
    vulnerabilities_found: int
    overall_score: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    target_health: TargetHealthStatus | None = None
    health_probe_passed: bool | None = None
    health_failure_reason: str | None = None
    recent_health_signature: str | None = None
    invalid_response_ratio: float | None = None

    model_config = {"from_attributes": True}


class ScanProgress(BaseModel):
    task_id: str
    status: str
    total: int
    completed: int
    vulnerabilities_found: int
    current_attack: str | None = None
    current_category: str | None = None
    probe_runtime_state: Literal["pending", "verified", "failed", "inconclusive", "skipped"] | None = None
    probe_case_id: str | None = None
    target_health: TargetHealthStatus | None = None
    health_probe_passed: bool | None = None
    health_failure_reason: str | None = None
    recent_health_signature: str | None = None
    invalid_response_ratio: float | None = None


class AttackResultResponse(BaseModel):
    id: str
    template_id: str
    category: str
    technique: str
    attack_name: str
    payload_text: str
    target_response: str | None
    attack_successful: bool
    confidence: float
    risk_level: str
    evidence: str | None
    leaked_info: str | None
    explanation: str | None
    remediation: str | None
    owasp_id: str | None
    risk_score: float
    verdict_status: str | None = None
    verdict_reason: str | None = None
    rule_hits: list[dict] = Field(default_factory=list)
    canary_provenance: dict | None = None
    execution_mode: str | None = None
    blackbox_outcome: str | None = None
    behavior_flags: dict[str, bool | None] = Field(default_factory=dict)
    attack_goal_score: float | None = None
    utility_score: float | None = None
    utility_explanation: str | None = None
    control_assessment: str | None = None
    control_summary: str | None = None
    case_id: str | None = None
    case_final_outcome: str | None = None
    quartet_present: bool | None = None
    business_verification_status: BusinessVerificationStatus | str | None = None
    probe_summary: dict | None = None
    probe_evidence_preview: list[dict] = Field(default_factory=list)
    concealment_class: str = "not_applicable"
    is_concealed: bool = False
    response_evaluation: ResponseEvaluationResponse | None = None
    analysis_raw: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttackResultReviewRequest(BaseModel):
    verdict_status: Literal["manual_verified", "false_positive", "reset"]
    review_note: str | None = None
