from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal[
    "curated_gold_seed",
    "manual_review_promoted",
    "production_random",
    "production_targeted",
]


class JudgeGoldLabel(BaseModel):
    """Minimum structured gold label — must be comparable across label versions."""
    reportable: bool
    verdict_status: str
    execution_mode: str | None = None
    blackbox_outcome: str | None = None


class JudgeCalibrationSampleCreate(BaseModel):
    attack_case_id: str | None = None
    source_type: SourceType
    sampling_reason: str | None = None
    is_drift_sample: bool = False
    label_version: str = "v1"
    # Optionally supply gold label at creation time
    gold_label: JudgeGoldLabel | None = None
    gold_rationale: str | None = None
    labeler: str | None = None


class JudgeCalibrationSampleUpdate(BaseModel):
    gold_label: JudgeGoldLabel | None = None
    gold_rationale: str | None = None
    labeler: str | None = None
    label_version: str | None = None
    is_drift_sample: bool | None = None


class JudgeCalibrationSampleBatchDelete(BaseModel):
    """Body for bulk-deleting a specific set of calibration samples by id.

    We use POST + body (rather than DELETE + body) because many HTTP
    intermediaries and clients strip the body from DELETE requests.
    """
    ids: list[str]


class JudgeCalibrationSampleResponse(BaseModel):
    id: str
    source_type: str
    attack_case_id: str | None
    judge_input_snapshot: dict | None
    judge_output: dict | None
    gold_label: dict | None
    gold_rationale: str | None
    labeler: str | None
    label_version: str
    sampling_reason: str | None
    is_drift_sample: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JudgeMisclassificationPreview(BaseModel):
    sample_id: str
    attack_case_id: str | None
    # scan_id is read from judge_input_snapshot["scan_id"] at metrics time.
    # Required by the frontend to link from a misclassified sample to the
    # owning scan's /results page. Kept optional so samples frozen before
    # this field was introduced still render cleanly (the UI just hides the
    # link for those).
    scan_id: str | None = None
    judge_verdict: str | None
    gold_verdict: str | None
    judge_reportable: bool | None
    gold_reportable: bool | None
    mismatch_type: str  # "false_positive" | "false_negative" | "verdict_drift"


class JudgeCalibrationBreakdownItem(BaseModel):
    key: str
    sample_count: int
    precision: float | None
    false_positive_rate: float | None
    recall: float | None


class JudgeConfusionMatrix(BaseModel):
    """Raw confusion counts behind precision/recall/FPR.

    Exposed so the frontend can render a 2x2 TP/FP/TN/FN card, which is far
    more legible than a single 80% precision number (especially when N is
    small). ``evaluated`` is the number of samples that contributed a pair
    of concrete reportable values; samples with a null on either side are
    excluded from the matrix.
    """
    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0
    evaluated: int = 0


class JudgeCalibrationSummary(BaseModel):
    sample_count: int
    labeled_count: int
    judge_precision_at_gold: float | None
    judge_recall_at_gold: float | None
    judge_false_positive_rate: float | None
    manual_review_overturn_rate: float | None
    confusion_matrix: JudgeConfusionMatrix | None = None
    by_category: list[JudgeCalibrationBreakdownItem] = Field(default_factory=list)
    by_source_type: list[JudgeCalibrationBreakdownItem] = Field(default_factory=list)
    by_target_type: list[JudgeCalibrationBreakdownItem] = Field(default_factory=list)
    by_judge_version: list[JudgeCalibrationBreakdownItem] = Field(default_factory=list)
    by_business_verification_status: list[JudgeCalibrationBreakdownItem] = Field(default_factory=list)
    misclassified_samples: list[JudgeMisclassificationPreview] = Field(default_factory=list)


class JudgeCalibrationRunCreate(BaseModel):
    name: str | None = None
    run_mode: Literal["snapshot_eval"] = "snapshot_eval"
    filters_json: dict | None = None


class JudgeCalibrationRunResponse(BaseModel):
    id: str
    name: str | None
    run_mode: str
    filters_json: dict | None
    sample_count: int
    summary_json: dict | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
