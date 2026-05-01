"""Finalize stuck scans from persisted attack results (shared by scans + reports routes)."""

import logging
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models import ScanTask
from app.services.finding_classifier import is_confirmed_finding
from app.services.risk_scorer import compute_overall_score

logger = logging.getLogger(__name__)


async def finalize_stuck_scan_from_db(task_id: str, db: AsyncSession) -> dict:
    # Diagnostic: log who's calling this and why. A scan being marked
    # ``completed`` despite ``completed_attacks < total_attacks`` is
    # almost always the result of one of the pause / finalize-stuck
    # API endpoints being invoked — nothing else writes
    # ScanTask.status = "completed". When we see the diff-from-legacy
    # tool show surprising results, this trace tells us WHO called it.
    # Stack trace goes back through the FastAPI request path so we can
    # tell ``/scans/{id}/pause`` from ``/scans/{id}/finalize-stuck``
    # from ``/reports/{id}/finalize-stuck``.
    caller_stack = "".join(traceback.format_stack(limit=8))
    logger.warning(
        "finalize_stuck_scan_from_db called for task_id=%s at %s\n"
        "caller stack (most recent call last):\n%s",
        task_id,
        datetime.now(timezone.utc).isoformat(),
        caller_stack,
    )

    result = await db.execute(
        select(ScanTask).where(ScanTask.id == task_id).options(selectinload(ScanTask.results))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan task not found")
    if task.status == "completed" and task.overall_score is not None:
        return {
            "task_id": task_id,
            "overall_score": task.overall_score,
            "status": task.status,
            "completed_attacks": task.completed_attacks,
        }
    if task.status not in ("running", "pending", "cancelled", "failed"):
        raise AppException(400, f"Scan is not stuck (status={task.status})")
    if not task.results:
        raise AppException(400, "No attack results yet; cannot finalize")

    logger.warning(
        "finalize_stuck_scan_from_db will OVERRIDE scan %s: "
        "current status=%s, completed=%s/%s (partial!) → forcing status='completed'",
        task_id, task.status, task.completed_attacks, task.total_attacks,
    )

    all_results = [
        {
            "attack_successful": r.attack_successful,
            "risk_score": r.risk_score,
            "verdict_status": (r.analysis_raw or {}).get("verdict_status"),
            "target_response": r.target_response,
        }
        for r in task.results
    ]
    overall = compute_overall_score(all_results)
    task.overall_score = overall
    task.completed_attacks = len(task.results)
    # Use the shared finding classifier so recovery matches the live runner.
    # Historically this counted "attack_successful" alone, which diverged from
    # scan_runner._is_vuln_case and produced different vulnerability counts for
    # the same data depending on whether the scan completed normally or was
    # recovered.
    task.vulnerabilities_found = sum(1 for r in all_results if is_confirmed_finding(r))
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "task_id": task_id,
        "overall_score": overall,
        "status": task.status,
        "completed_attacks": task.completed_attacks,
    }
