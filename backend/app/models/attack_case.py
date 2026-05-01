import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttackCase(Base):
    __tablename__ = "attack_cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_tasks.id"), nullable=False
    )

    template_id: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    technique: Mapped[str] = mapped_column(String(100), nullable=False)
    attack_name: Mapped[str] = mapped_column(String(255), nullable=False)

    protocol_version: Mapped[str] = mapped_column(String(50), default="quartet_v1")
    case_status: Mapped[str] = mapped_column(String(20), default="pending")
    case_final_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attack_variant_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_assessment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    control_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verdict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    probe_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    probe_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Phase 4: judge calibration
    judge_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_required: Mapped[bool | None] = mapped_column(nullable=True)
    reportable: Mapped[bool | None] = mapped_column(nullable=True)
    legacy_attack_result_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("attack_results.id"), nullable=True, unique=True
    )
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    scan_task: Mapped["ScanTask"] = relationship(back_populates="attack_cases")
    variants: Mapped[list["AttackCaseVariant"]] = relationship(
        back_populates="attack_case",
        cascade="all, delete-orphan",
        order_by="AttackCaseVariant.position",
    )
    legacy_attack_result: Mapped["AttackResult | None"] = relationship(
        back_populates="attack_case",
        foreign_keys=[legacy_attack_result_id],
        uselist=False,
    )
