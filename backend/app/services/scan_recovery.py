"""Finalize stuck scans from persisted attack results (shared by scans + reports routes)."""

import logging
import traceback
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models import ScanTask, AttackResult
from app.services.finding_classifier import is_confirmed_finding
from app.services.risk_scorer import compute_overall_score, scoring_result_payload

logger = logging.getLogger(__name__)


async def finalize_stuck_scan_from_db(task_id: str, db: AsyncSession) -> dict:
    # Keep the caller trace to distinguish pause from manual recovery.
    caller_stack = "".join(traceback.format_stack(limit=8))
    logger.warning(
        "finalize_stuck_scan_from_db called for task_id=%s at %s\n"
        "caller stack (most recent call last):\n%s",
        task_id,
        datetime.now(timezone.utc).isoformat(),
        caller_stack,
    )

    result = await db.execute(
        select(ScanTask).where(ScanTask.id == task_id).options(
            selectinload(ScanTask.results).selectinload(AttackResult.attack_case)
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan task not found")
    if task.status == "completed":
        return {
            "task_id": task_id,
            "overall_score": task.overall_score,
            "status": task.status,
            "completed_attacks": task.completed_attacks,
        }
    if task.status not in ("running", "pending", "cancelled", "failed"):
        raise AppException(400, f"Scan is not stuck (status={task.status})")

    all_results = [scoring_result_payload(r) for r in task.results]
    overall = compute_overall_score(all_results, expected_tests=task.total_attacks)
    task.overall_score = overall
    task.completed_attacks = len(task.results)
    # Use the shared finding classifier so recovery matches the live runner.
    # Historically this counted "attack_successful" alone, which diverged from
    # scan_runner._is_vuln_case and produced different vulnerability counts for
    # the same data depending on whether the scan completed normally or was
    # recovered.
    task.vulnerabilities_found = sum(1 for r in all_results if is_confirmed_finding(r))
    if task.status in {"running", "pending"}:
        final_status = (
            "completed"
            if task.total_attacks > 0 and task.completed_attacks >= task.total_attacks
            else "cancelled"
        )
        await db.execute(
            update(ScanTask)
            .where(ScanTask.id == task_id, ScanTask.status.in_(("running", "pending")))
            .values(status=final_status, completed_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
    elif task.completed_at is None:
        await db.execute(
            update(ScanTask)
            .where(ScanTask.id == task_id, ScanTask.completed_at.is_(None))
            .values(completed_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
    await db.commit()
    await db.refresh(task, attribute_names=["status", "completed_at"])
    return {
        "task_id": task_id,
        "overall_score": overall,
        "status": task.status,
        "completed_attacks": task.completed_attacks,
    }
