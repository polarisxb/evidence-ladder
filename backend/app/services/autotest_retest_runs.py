"""Persistence helpers for auditable AutoTest retest runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AutoTestRetestRun, ScanTask


def extract_retest_metadata(runtime_vars: Any) -> dict[str, Any] | None:
    if not isinstance(runtime_vars, Mapping):
        return None

    namespaced = runtime_vars.get("autotest_retest")
    metadata = namespaced if isinstance(namespaced, Mapping) else runtime_vars

    source_scan_id = _optional_str(metadata.get("source_scan_id"))
    source_result_ids = _string_list(metadata.get("source_result_ids"))
    if not source_scan_id or not source_result_ids:
        return None

    return {
        "source_scan_id": source_scan_id,
        "source_result_ids": source_result_ids,
        "retest_reason": _optional_str(metadata.get("retest_reason")) or "unknown",
        "retest_type": _optional_str(metadata.get("retest_type")) or "quartet",
    }


async def record_retest_run_for_scan(
    task: ScanTask,
    db: AsyncSession,
) -> AutoTestRetestRun | None:
    metadata = extract_retest_metadata(task.runtime_vars)
    if metadata is None:
        return None

    existing = await get_retest_run_for_scan(task.id, db)
    if existing is not None:
        return existing

    run = AutoTestRetestRun(
        source_scan_id=metadata["source_scan_id"],
        retest_scan_id=task.id,
        source_result_ids=metadata["source_result_ids"],
        retest_reason=metadata["retest_reason"],
        retest_type=metadata["retest_type"],
        status="created",
        outcome_counts={},
        comparison_snapshot=[],
    )
    db.add(run)
    await db.flush()
    return run


async def get_retest_run_for_scan(
    scan_id: str,
    db: AsyncSession,
) -> AutoTestRetestRun | None:
    result = await db.execute(
        select(AutoTestRetestRun).where(AutoTestRetestRun.retest_scan_id == scan_id)
    )
    return result.scalar_one_or_none()


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for text in (_optional_str(item) for item in value) if text]
    if isinstance(value, tuple):
        return [text for text in (_optional_str(item) for item in value) if text]
    text = _optional_str(value)
    return [text] if text else []
