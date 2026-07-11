import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseRetestLineage(Base):
    """Auditable ``initial → retest_1 → … → final`` lineage for one case.

    Produced by ``retest_loop.run_retest_loop_async`` and persisted per case so
    the experiment (Arm A vs Arm B) can be reconstructed and the "extra query
    cost" of the retest loop reported. ``lineage_json`` is the full
    ``RetestLineage.to_dict()``; the scalar columns are denormalised for
    grouped querying/metrics.
    """

    __tablename__ = "case_retest_lineages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    arm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retest_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    initial_evidence_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    final_evidence_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    converged_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_extra_queries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_extra_cost_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lineage_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    scan_task: Mapped["ScanTask"] = relationship("ScanTask")
