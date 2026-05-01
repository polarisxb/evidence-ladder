from pydantic import BaseModel, Field
from typing import Literal


class CategoryScore(BaseModel):
    category: str
    category_name: str
    owasp_id: str
    score: float
    pass_rate: float
    attack_success_rate: float
    total_tests: int
    successful_attacks: int
    failed_attacks: int
    risk_level: str


class SecurityReport(BaseModel):
    scan_id: str
    scan_name: str
    target_url: str
    overall_score: float
    security_posture_score: float
    risk_level: str
    total_attacks: int
    completed_attacks: int
    # NOTE: Raw count of cases where the AI judge set ``attack_successful=True``
    # before the verdict engine overlay. This is NOT the headline "Vulnerabilities
    # Found" number — that is ``confirmed_findings`` (= confirmed + suspected)
    # and matches the DB column ``scan_tasks.vulnerabilities_found`` as well as
    # the ``Confirmed Findings`` card in the frontend report and HTML export.
    # ``successful_attacks`` is kept for backward compatibility with older API
    # consumers; new consumers should prefer ``confirmed_findings``.
    successful_attacks: int
    attack_success_rate: float
    severity_ratio: float
    average_finding_severity: float | None
    average_attack_goal_score: float | None
    average_utility_score: float | None
    utility_scored_results: int
    finding_breakdown: dict[str, int]
    # Verdict-based finding distribution (single source of truth shared with
    # ``scan_runner`` / ``scan_recovery`` via ``finding_classifier``). Unlike
    # ``finding_breakdown`` (keyed by raw ``verdict_status``), these buckets
    # map each case to exactly one of six ``FindingClass`` values so the UI
    # can render a layered summary without double-counting.
    finding_counts: dict[str, int] = Field(default_factory=dict)
    confirmed_findings: int = 0
    needs_review_count: int = 0
    false_positive_count: int = 0
    blackbox_outcome_breakdown: dict[str, int]
    business_verification_breakdown: dict[str, int] = Field(default_factory=dict)
    target_health: str | None = None
    health_probe_passed: bool | None = None
    health_failure_reason: str | None = None
    recent_health_signature: str | None = None
    invalid_response_ratio: float | None = None
    category_scores: list[CategoryScore]
    critical_findings: list[dict]
    high_findings: list[dict]
    medium_findings: list[dict]
    low_findings: list[dict]
    recommendations: list[str]


class CvssMetrics(BaseModel):
    attack_vector: Literal["N", "A", "L", "P"] = "N"
    attack_complexity: Literal["L", "H"] = "L"
    privileges_required: Literal["N", "L", "H"] = "N"
    user_interaction: Literal["N", "P", "A"] = "N"
    confidentiality: Literal["H", "L", "N"] = "N"
    integrity: Literal["H", "L", "N"] = "N"
    availability: Literal["H", "L", "N"] = "N"


class BehaviorFlags(BaseModel):
    discussion_only: bool = False
    attack_obedience: bool = False
    task_deviation: bool = False
    secret_disclosure: bool = False
    unauthorized_action_claim: bool = False
    original_task_completed: bool | None = None


class AnalysisResult(BaseModel):
    attack_successful: bool
    confidence: float
    risk_level: str
    evidence: str
    leaked_info: str | None = None
    explanation: str
    cvss_metrics: CvssMetrics | None = None
    remediation: str | None = None
    execution_mode: str = "UNCERTAIN"
    blackbox_outcome: str = "NO_INJECTION_SUCCESS"
    behavior_flags: BehaviorFlags = Field(default_factory=BehaviorFlags)
    attack_goal_score: float | None = None
    utility_score: float | None = None
    utility_explanation: str | None = None
