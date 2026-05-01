import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanTask(Base):
    __tablename__ = "scan_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), default="Untitled Scan")
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | running | completed | failed | cancelled

    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(50), default="openai_compatible"
    )  # openai_compatible | custom | builtin_vulnerable | adapter
    adapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("adapters.id", ondelete="SET NULL"), nullable=True
    )
    target_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    runtime_vars: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    attack_categories: Mapped[list] = mapped_column(JSON, default=list)
    advanced_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_attacks: Mapped[int] = mapped_column(Integer, default=0)
    completed_attacks: Mapped[int] = mapped_column(Integer, default=0)
    vulnerabilities_found: Mapped[int] = mapped_column(Integer, default=0)
    target_health: Mapped[str | None] = mapped_column(String(20), nullable=True)
    health_probe_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    health_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recent_health_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalid_response_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    results: Mapped[list["AttackResult"]] = relationship(
        back_populates="scan_task", cascade="all, delete-orphan"
    )
    attack_cases: Mapped[list["AttackCase"]] = relationship(
        back_populates="scan_task", cascade="all, delete-orphan"
    )
    adapter: Mapped["Adapter | None"] = relationship(back_populates="scans")
