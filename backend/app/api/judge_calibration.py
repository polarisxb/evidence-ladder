import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.models.attack_case import AttackCase
from app.models.judge_calibration_run import JudgeCalibrationRun
from app.models.judge_calibration_sample import JudgeCalibrationSample
from app.schemas.judge_calibration import (
    JudgeCalibrationRunCreate,
    JudgeCalibrationRunResponse,
    JudgeCalibrationSampleBatchDelete,
    JudgeCalibrationSampleCreate,
    JudgeCalibrationSampleResponse,
    JudgeCalibrationSampleUpdate,
    JudgeCalibrationSummary,
)
from app.services.judge_calibration_runner import run_calibration
from app.services.judge_metrics import compute_calibration_metrics
from app.services.judge_sampling import (
    batch_sample_production,
    find_existing_sample,
    ingest_sample,
    list_samples,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Samples ──────────────────────────────────────────────────────────────────

@router.post("/samples", response_model=dict)
async def create_calibration_sample(
    body: JudgeCalibrationSampleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a calibration sample from a specific attack_case_id.

    Returns 409 if a sample with the same (attack_case_id, source_type, label_version)
    already exists, to prevent unbounded duplicate growth.
    """
    if not body.attack_case_id:
        raise AppException(400, "attack_case_id is required")

    # Dedup guard
    existing = await find_existing_sample(
        db,
        attack_case_id=body.attack_case_id,
        source_type=body.source_type,
        label_version=body.label_version,
    )
    if existing is not None:
        raise AppException(
            409,
            f"A sample for case {body.attack_case_id} with source_type={body.source_type!r} "
            f"and label_version={body.label_version!r} already exists (id={existing.id}). "
            "Use PATCH to update the gold label.",
        )

    result = await db.execute(select(AttackCase).where(AttackCase.id == body.attack_case_id))
    attack_case = result.scalar_one_or_none()
    if not attack_case:
        raise AppException(404, f"AttackCase {body.attack_case_id} not found")

    sample = await ingest_sample(
        db,
        attack_case,
        source_type=body.source_type,
        sampling_reason=body.sampling_reason,
        label_version=body.label_version,
        is_drift_sample=body.is_drift_sample,
    )
    # Apply gold label if provided at creation time
    if body.gold_label is not None:
        sample.gold_label = body.gold_label.model_dump()
        sample.gold_rationale = body.gold_rationale
        sample.labeler = body.labeler
    await db.commit()
    await db.refresh(sample)
    return {"data": JudgeCalibrationSampleResponse.model_validate(sample).model_dump(), "message": "ok"}


@router.post("/samples/batch", response_model=dict)
async def batch_create_calibration_samples(
    limit: int = Query(default=50, ge=1, le=500),
    category: str | None = None,
    business_verification_status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Batch-ingest production cases as calibration samples using stratified sampling.

    Automatically deduplicates: cases already ingested as production samples are skipped.
    Returns the newly created samples.
    """
    filters: dict = {}
    if category:
        filters["category"] = category
    if business_verification_status:
        filters["business_verification_status"] = business_verification_status

    new_samples = await batch_sample_production(db, limit=limit, filters=filters)
    return {
        "data": [JudgeCalibrationSampleResponse.model_validate(s).model_dump() for s in new_samples],
        "count": len(new_samples),
        "message": f"{len(new_samples)} sample(s) ingested",
    }


@router.get("/samples", response_model=dict)
async def list_calibration_samples(
    source_type: str | None = None,
    label_version: str | None = None,
    has_gold_label: bool | None = None,
    is_drift_sample: bool | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    samples = await list_samples(
        db,
        source_type=source_type,
        label_version=label_version,
        has_gold_label=has_gold_label,
        is_drift_sample=is_drift_sample,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [JudgeCalibrationSampleResponse.model_validate(s).model_dump() for s in samples],
        "count": len(samples),
        "message": "ok",
    }


@router.patch("/samples/{sample_id}", response_model=dict)
async def update_calibration_sample(
    sample_id: str,
    body: JudgeCalibrationSampleUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JudgeCalibrationSample).where(JudgeCalibrationSample.id == sample_id)
    )
    sample = result.scalar_one_or_none()
    if not sample:
        raise AppException(404, f"Sample {sample_id} not found")

    if body.gold_label is not None:
        sample.gold_label = body.gold_label.model_dump()
    if body.gold_rationale is not None:
        sample.gold_rationale = body.gold_rationale
    if body.labeler is not None:
        sample.labeler = body.labeler
    if body.label_version is not None:
        sample.label_version = body.label_version
    if body.is_drift_sample is not None:
        sample.is_drift_sample = body.is_drift_sample

    await db.commit()
    await db.refresh(sample)
    return {"data": JudgeCalibrationSampleResponse.model_validate(sample).model_dump(), "message": "ok"}


@router.delete("/samples/{sample_id}", response_model=dict)
async def delete_calibration_sample(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a calibration sample.

    The sample is a detached, frozen snapshot of (attack_case, judge_output)
    — deleting it does NOT touch the underlying AttackCase or ScanTask, only
    the calibration record. This is intentionally a hard delete rather than
    soft-delete because calibration samples are disposable artifacts: users
    routinely re-sample to refresh the dataset, and keeping soft-deleted rows
    would distort the precision/recall counts on the Calibration page.
    """
    result = await db.execute(
        select(JudgeCalibrationSample).where(JudgeCalibrationSample.id == sample_id)
    )
    sample = result.scalar_one_or_none()
    if not sample:
        raise AppException(404, f"Sample {sample_id} not found")

    await db.delete(sample)
    await db.commit()
    return {"data": {"id": sample_id}, "message": "deleted"}


@router.post("/samples/delete-batch", response_model=dict)
async def delete_calibration_samples_batch(
    body: JudgeCalibrationSampleBatchDelete,
    db: AsyncSession = Depends(get_db),
):
    """Bulk-delete a specific set of calibration samples by id.

    Returns the number of rows actually deleted. Missing ids are silently
    ignored rather than raising 404, so the caller can fire-and-forget
    without pre-checking existence — useful when the UI selection can race
    with a concurrent delete from another tab.
    """
    if not body.ids:
        return {"data": {"deleted": 0}, "message": "ok"}

    stmt = (
        delete(JudgeCalibrationSample)
        .where(JudgeCalibrationSample.id.in_(body.ids))
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"data": {"deleted": int(result.rowcount or 0)}, "message": "deleted"}


@router.delete("/samples", response_model=dict)
async def delete_all_calibration_samples(
    source_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Delete ALL calibration samples, optionally filtered by source_type.

    This is intentionally a separate endpoint (not just ``POST
    /samples/delete-batch`` with every id) so the UI doesn't have to
    enumerate potentially thousands of ids, and so the destructive intent
    is explicit at the HTTP layer. Protect in the UI with a confirm dialog.
    """
    stmt = delete(JudgeCalibrationSample)
    if source_type is not None:
        stmt = stmt.where(JudgeCalibrationSample.source_type == source_type)
    result = await db.execute(stmt)
    await db.commit()
    return {"data": {"deleted": int(result.rowcount or 0)}, "message": "deleted"}


# ─── Runs ─────────────────────────────────────────────────────────────────────

@router.post("/runs", response_model=dict)
async def create_calibration_run(
    body: JudgeCalibrationRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create and immediately execute a calibration run."""
    run = JudgeCalibrationRun(
        id=str(uuid.uuid4()),
        name=body.name,
        run_mode=body.run_mode,
        filters_json=body.filters_json,
    )
    db.add(run)
    await db.flush()
    await db.commit()

    try:
        run = await run_calibration(db, run.id)
    except Exception as exc:
        logger.error("Calibration run %s failed: %s", run.id, exc)
        # run record already has status=failed after run_calibration raises

    await db.refresh(run)
    return {"data": JudgeCalibrationRunResponse.model_validate(run).model_dump(), "message": "ok"}


@router.get("/runs", response_model=dict)
async def list_calibration_runs(
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List calibration runs, newest first.

    Returns a lightweight projection suitable for a history panel — the
    full ``summary_json`` (which may be large) is still included so the UI
    can render per-run metrics without a second round trip.
    """
    result = await db.execute(
        select(JudgeCalibrationRun)
        .order_by(JudgeCalibrationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = list(result.scalars().all())
    return {
        "data": [JudgeCalibrationRunResponse.model_validate(r).model_dump() for r in runs],
        "count": len(runs),
        "message": "ok",
    }


@router.get("/runs/{run_id}", response_model=dict)
async def get_calibration_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JudgeCalibrationRun).where(JudgeCalibrationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise AppException(404, f"Calibration run {run_id} not found")
    return {"data": JudgeCalibrationRunResponse.model_validate(run).model_dump(), "message": "ok"}


# ─── Summary ──────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=dict)
async def get_calibration_summary(
    label_version: str | None = None,
    source_type: str | None = None,
    category: str | None = None,
    target_type: str | None = None,
    judge_version: str | None = None,
    business_verification_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated calibration summary across all labeled samples.

    Supports filtering by label_version, source_type, category, target_type,
    business_verification_status, date_from, and date_to.
    """
    # Build combined filter dict (label_version/source_type go to list_samples,
    # the rest are passed through to _load_samples-style post-filtering)
    from datetime import datetime as _dt

    extra_filters: dict = {}
    if category:
        extra_filters["category"] = category
    if target_type:
        extra_filters["target_type"] = target_type
    if business_verification_status:
        extra_filters["business_verification_status"] = business_verification_status

    samples = await list_samples(
        db,
        source_type=source_type,
        label_version=label_version,
        has_gold_label=True,
        date_from=_dt.fromisoformat(date_from) if date_from else None,
        date_to=_dt.fromisoformat(date_to) if date_to else None,
        limit=5000,
    )

    if judge_version:
        extra_filters["judge_version"] = judge_version

    # Apply JSON-embedded field filters in Python
    if extra_filters:
        filtered = []
        for s in samples:
            snap = s.judge_input_snapshot or {}
            out = s.judge_output or {}
            if category and snap.get("category") != category:
                continue
            if target_type and snap.get("target_type") != target_type:
                continue
            if judge_version and out.get("judge_version") != judge_version:
                continue
            if business_verification_status and snap.get("business_verification_status") != business_verification_status:
                continue
            filtered.append(s)
        samples = filtered
    if not samples:
        summary = JudgeCalibrationSummary(
            sample_count=0,
            labeled_count=0,
            judge_precision_at_gold=None,
            judge_recall_at_gold=None,
            judge_false_positive_rate=None,
            manual_review_overturn_rate=None,
        )
    else:
        summary = compute_calibration_metrics(samples)
    return {"data": summary.model_dump(), "message": "ok"}
