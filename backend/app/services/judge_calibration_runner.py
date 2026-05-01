"""Calibration run executor.

Operates on frozen sample snapshots only — never re-accesses live targets or probes.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.judge_calibration_run import JudgeCalibrationRun
from app.models.judge_calibration_sample import JudgeCalibrationSample
from app.services.judge_metrics import compute_calibration_metrics


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def run_calibration(db: AsyncSession, run_id: str) -> JudgeCalibrationRun:
    """Execute a calibration run identified by run_id.

    Loads all samples (applying filters from run.filters_json if any),
    computes metrics, and writes results back to the run record.
    """
    result = await db.execute(
        select(JudgeCalibrationRun).where(JudgeCalibrationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"Calibration run {run_id} not found")
    if run.status not in ("pending", "failed"):
        raise ValueError(f"Run {run_id} is already {run.status}")

    run.status = "running"
    run.started_at = _utcnow()
    await db.flush()

    try:
        samples = await _load_samples(db, run.filters_json)
        summary = compute_calibration_metrics(samples)
        run.status = "completed"
        run.completed_at = _utcnow()
        run.sample_count = len(samples)
        run.summary_json = summary.model_dump()
    except Exception as exc:
        run.status = "failed"
        run.completed_at = _utcnow()
        run.summary_json = {"error": str(exc)}
        await db.commit()
        raise

    await db.commit()
    await db.refresh(run)
    return run


async def _load_samples(
    db: AsyncSession,
    filters: dict | None,
) -> list[JudgeCalibrationSample]:
    """Load calibration samples, applying DB-level filters where possible and
    Python-side filters for JSON-embedded fields (category, target_type, bvs).
    """
    stmt = select(JudgeCalibrationSample)
    filters = filters or {}

    # DB-level filters on dedicated columns
    if filters.get("source_type"):
        stmt = stmt.where(JudgeCalibrationSample.source_type == filters["source_type"])
    if filters.get("label_version"):
        stmt = stmt.where(JudgeCalibrationSample.label_version == filters["label_version"])
    if filters.get("has_gold_label") is True:
        stmt = stmt.where(JudgeCalibrationSample.gold_label.isnot(None))
    if filters.get("date_from"):
        stmt = stmt.where(JudgeCalibrationSample.created_at >= filters["date_from"])
    if filters.get("date_to"):
        stmt = stmt.where(JudgeCalibrationSample.created_at <= filters["date_to"])

    result = await db.execute(stmt)
    samples = list(result.scalars().all())

    # Python-side filters for JSON snapshot fields (category, target_type, bvs)
    category_filter = filters.get("category")
    target_type_filter = filters.get("target_type")
    bvs_filter = filters.get("business_verification_status")

    if category_filter or target_type_filter or bvs_filter:
        filtered = []
        for s in samples:
            snap = s.judge_input_snapshot or {}
            if category_filter and snap.get("category") != category_filter:
                continue
            if target_type_filter and snap.get("target_type") != target_type_filter:
                continue
            if bvs_filter and snap.get("business_verification_status") != bvs_filter:
                continue
            filtered.append(s)
        return filtered

    return samples
