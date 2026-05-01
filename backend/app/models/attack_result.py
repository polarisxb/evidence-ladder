import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttackResult(Base):
    __tablename__ = "attack_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_tasks.id"), nullable=False
    )

    template_id: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    technique: Mapped[str] = mapped_column(String(100), nullable=False)
    attack_name: Mapped[str] = mapped_column(String(255), nullable=False)

    payload_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_response: Mapped[str] = mapped_column(Text, nullable=True)

    attack_successful: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(
        String(20), default="none"
    )  # critical | high | medium | low | none
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    leaked_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)

    owasp_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)

    analysis_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    scan_task: Mapped["ScanTask"] = relationship(back_populates="results")
    attack_case: Mapped["AttackCase | None"] = relationship(
        back_populates="legacy_attack_result", uselist=False
    )
