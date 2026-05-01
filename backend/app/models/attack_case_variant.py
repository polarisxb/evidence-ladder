import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttackCaseVariant(Base):
    __tablename__ = "attack_case_variants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    attack_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attack_cases.id"), nullable=False
    )

    variant_type: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    attack_case: Mapped["AttackCase"] = relationship(back_populates="variants")
