"""Judge calibration sampling service.

Responsibilities:
- Build frozen judge_input_snapshot and judge_output from an AttackCase
- Ingest individual samples into judge_calibration_samples
- List / filter samples
- Batch production sampling with minimal stratification
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attack_case import AttackCase
from app.models.judge_calibration_sample import JudgeCalibrationSample
from app.models.scan_task import ScanTask


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_TARGETED_VERDICT_STATUSES = {"manual_review_needed", "ai_suspected"}
_TARGETED_BVS = {"text_claim_only", "probe_failed"}
_TARGETED_CONTROL = {"controls_inconclusive"}


def sample_from_case(
    attack_case: AttackCase,
    *,
    target_type: str | None = None,
) -> tuple[dict, dict]:
    """Return (judge_input_snapshot, judge_output) frozen from the case.

    judge_input_snapshot  — evidence the judge sees (case-level summary)
    judge_output          — the automatic judge decision (judge_snapshot)

    Pass target_type explicitly when available to enable by_target_type breakdowns
    in calibration metrics.  If omitted, target_type is omitted from the snapshot.
    """
    summary = attack_case.summary_json or {}
    judge_snapshot = attack_case.judge_snapshot or {}

    judge_input_snapshot: dict = {
        "case_id": attack_case.id,
        # scan_id is the user-facing owner of this case. The UI uses it to
        # deep-link from a sample back to /results/:scanId so annotators can
        # inspect the full attack context. Without this field the Calibration
        # page would have to guess the scan id from attack_case_id (there is
        # no such route), leading to "Scan not found" errors.
        "scan_id": attack_case.scan_task_id,
        "category": attack_case.category,
        "technique": attack_case.technique,
        "attack_name": attack_case.attack_name,
        "case_final_outcome": attack_case.case_final_outcome,
        "control_assessment": attack_case.control_assessment,
        "control_summary": attack_case.control_summary,
        "business_verification_status": attack_case.business_verification_status,
        "quartet_present": summary.get("quartet_present"),
        "primary_attack_successful": summary.get("primary_attack_successful"),
        "attack_goal_score": judge_snapshot.get("attack_goal_score"),
        "utility_score": judge_snapshot.get("utility_score"),
        "execution_mode": judge_snapshot.get("execution_mode"),
        "blackbox_outcome": judge_snapshot.get("blackbox_outcome"),
        "frozen_at": _utcnow().isoformat(),
    }
    if target_type is not None:
        judge_input_snapshot["target_type"] = target_type

    judge_output = {
        "verdict_status": judge_snapshot.get("verdict_status"),
        "verdict_reason": judge_snapshot.get("verdict_reason"),
        "execution_mode": judge_snapshot.get("execution_mode"),
        "blackbox_outcome": judge_snapshot.get("blackbox_outcome"),
        "reportable": judge_snapshot.get("reportable"),
        "review_required": judge_snapshot.get("review_required"),
    }

    return judge_input_snapshot, judge_output


async def find_existing_sample(
    db: AsyncSession,
    attack_case_id: str,
    source_type: str,
    label_version: str,
) -> JudgeCalibrationSample | None:
    """Return an existing sample for the same (attack_case_id, source_type, label_version), or None."""
    result = await db.execute(
        select(JudgeCalibrationSample)
        .where(JudgeCalibrationSample.attack_case_id == attack_case_id)
        .where(JudgeCalibrationSample.source_type == source_type)
        .where(JudgeCalibrationSample.label_version == label_version)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ingest_sample(
    db: AsyncSession,
    attack_case: AttackCase,
    source_type: str,
    sampling_reason: str | None = None,
    label_version: str = "v1",
    is_drift_sample: bool = False,
    *,
    target_type: str | None = None,
) -> JudgeCalibrationSample:
    """Create a new calibration sample from an AttackCase and flush it to the DB.

    Does NOT check for duplicates — callers that want dedup should call
    find_existing_sample() first (or use batch_sample_production which deduplicates).
    """
    judge_input_snapshot, judge_output = sample_from_case(attack_case, target_type=target_type)
    sample = JudgeCalibrationSample(
        id=str(uuid.uuid4()),
        source_type=source_type,
        attack_case_id=attack_case.id,
        judge_input_snapshot=judge_input_snapshot,
        judge_output=judge_output,
        label_version=label_version,
        sampling_reason=sampling_reason,
        is_drift_sample=is_drift_sample,
    )
    db.add(sample)
    await db.flush()
    return sample


async def list_samples(
    db: AsyncSession,
    *,
    source_type: str | None = None,
    label_version: str | None = None,
    has_gold_label: bool | None = None,
    is_drift_sample: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[JudgeCalibrationSample]:
    stmt = select(JudgeCalibrationSample)
    if source_type is not None:
        stmt = stmt.where(JudgeCalibrationSample.source_type == source_type)
    if label_version is not None:
        stmt = stmt.where(JudgeCalibrationSample.label_version == label_version)
    if has_gold_label is True:
        stmt = stmt.where(JudgeCalibrationSample.gold_label.isnot(None))
    elif has_gold_label is False:
        stmt = stmt.where(JudgeCalibrationSample.gold_label.is_(None))
    if is_drift_sample is not None:
        stmt = stmt.where(JudgeCalibrationSample.is_drift_sample == is_drift_sample)
    if date_from is not None:
        stmt = stmt.where(JudgeCalibrationSample.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(JudgeCalibrationSample.created_at <= date_to)
    stmt = stmt.order_by(JudgeCalibrationSample.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def batch_sample_production(
    db: AsyncSession,
    limit: int = 50,
    *,
    filters: dict | None = None,
) -> list[JudgeCalibrationSample]:
    """Pull recent production cases and ingest them as production_random/targeted samples.

    Uses minimal stratification: prioritises targeted cases (inconclusive verdict,
    text_claim_only/probe_failed, or high-risk low-confidence).
    Deduplicates by (attack_case_id, source_type, label_version) to avoid unbounded growth.
    """
    filters = filters or {}
    stmt = (
        select(AttackCase)
        .where(AttackCase.case_status == "completed")
        .where(AttackCase.judge_snapshot.isnot(None))
        .order_by(AttackCase.created_at.desc())
        .limit(limit * 3)  # over-fetch for stratification
    )
    if filters.get("category"):
        stmt = stmt.where(AttackCase.category == filters["category"])
    if filters.get("business_verification_status"):
        stmt = stmt.where(
            AttackCase.business_verification_status == filters["business_verification_status"]
        )

    result = await db.execute(stmt)
    cases = list(result.scalars().all())

    # Deduplicate: skip cases already ingested as production samples
    if cases:
        case_ids = [c.id for c in cases]
        existing_result = await db.execute(
            select(JudgeCalibrationSample.attack_case_id)
            .where(JudgeCalibrationSample.attack_case_id.in_(case_ids))
            .where(
                JudgeCalibrationSample.source_type.in_(
                    {"production_random", "production_targeted"}
                )
            )
        )
        already_sampled = {row[0] for row in existing_result}
        cases = [c for c in cases if c.id not in already_sampled]

    # Resolve target_type from parent scan tasks (for by_target_type metrics)
    target_type_map: dict[str, str | None] = {}
    if cases:
        scan_ids = list({c.scan_task_id for c in cases})
        scan_result = await db.execute(
            select(ScanTask.id, ScanTask.target_type).where(ScanTask.id.in_(scan_ids))
        )
        scan_target_types = {row.id: row.target_type for row in scan_result}
        target_type_map = {c.id: scan_target_types.get(c.scan_task_id) for c in cases}

    # Separate targeted from random
    targeted = []
    random_pool = []
    for case in cases:
        snap = case.judge_snapshot or {}
        verdict = snap.get("verdict_status")
        bvs = case.business_verification_status
        ctrl = case.control_assessment
        if verdict in _TARGETED_VERDICT_STATUSES or bvs in _TARGETED_BVS or ctrl in _TARGETED_CONTROL:
            targeted.append(case)
        else:
            random_pool.append(case)

    selected = targeted[:limit // 2] + random_pool[:limit - len(targeted[:limit // 2])]
    selected = selected[:limit]

    new_samples: list[JudgeCalibrationSample] = []
    for case in selected:
        source = (
            "production_targeted"
            if (case.judge_snapshot or {}).get("verdict_status") in _TARGETED_VERDICT_STATUSES
            else "production_random"
        )
        sample = await ingest_sample(
            db,
            case,
            source_type=source,
            sampling_reason="batch_production_sampling",
            target_type=target_type_map.get(case.id),
        )
        new_samples.append(sample)

    await db.commit()
    return new_samples
