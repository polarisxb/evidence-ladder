import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutoTestRetestRun(Base):
    __tablename__ = "autotest_retest_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    retest_scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_tasks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source_result_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    retest_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    retest_type: Mapped[str] = mapped_column(String(50), default="quartet", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    outcome_counts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    comparison_snapshot: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    source_scan: Mapped["ScanTask"] = relationship(
        "ScanTask",
        foreign_keys=[source_scan_id],
    )
    retest_scan: Mapped["ScanTask"] = relationship(
        "ScanTask",
        foreign_keys=[retest_scan_id],
    )
