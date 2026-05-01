import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JudgeCalibrationSample(Base):
    __tablename__ = "judge_calibration_samples"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 来源类型: curated_gold_seed | manual_review_promoted | production_random | production_targeted
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    attack_case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("attack_cases.id", ondelete="SET NULL"), nullable=True
    )
    # 冻结的 judge 输入快照（case 证据）
    judge_input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # judge 自动输出（judge_snapshot 字段的冻结副本）
    judge_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 人工 gold label
    gold_label: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gold_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    labeler: Mapped[str | None] = mapped_column(String(100), nullable=True)
    label_version: Mapped[str] = mapped_column(String(20), default="v1")
    sampling_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_drift_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
