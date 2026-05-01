"""Build executable AutoTest retest drafts from weak evidence findings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models import ScanTask
from app.schemas.autotest import AutoTestRetestDraftResponse
from app.schemas.scan import AdvancedConfig, ScanCreate, TargetConfig
from app.services.autotest_summary import build_autotest_summary


async def build_quartet_retest_draft(scan_id: str, db: AsyncSession) -> AutoTestRetestDraftResponse:
    task = await _load_scan(scan_id, db)
    summary = await build_autotest_summary(scan_id, db)

    quartet_actions = [
        group
        for group in summary.retest_actions
        if any(action.get("action_type") == "run_quartet" for action in group.actions)
    ]
    if not quartet_actions:
        raise AppException(400, "No quartet retest actions are available for this scan")

    categories = _dedupe(group.category for group in quartet_actions if group.category)
    source_result_ids = [group.result_id for group in quartet_actions]

    scan_config = ScanCreate(
        name=f"Retest: {task.name} (quartet evidence)",
        target_url=task.target_url,
        target_type=task.target_type,  # type: ignore[arg-type]
        adapter_id=task.adapter_id,
        target_config=_target_config(task.target_config),
        runtime_vars=_retest_runtime_vars(
            task.runtime_vars,
            source_scan_id=task.id,
            source_result_ids=source_result_ids,
            retest_reason="judge_without_rule_evidence",
            retest_type="quartet",
        ),
        attack_categories=categories or list(task.attack_categories or ["all"]),
        advanced=_quartet_retest_advanced(task.advanced_config),
        judge_provider_id=task.judge_provider_id,
        judge_model=task.judge_model,
        generation_provider_id=task.generation_provider_id,
        generation_model=task.generation_model,
    )

    return AutoTestRetestDraftResponse(
        source_scan_id=task.id,
        source_result_ids=source_result_ids,
        retest_reason="judge_without_rule_evidence",
        action_count=len(quartet_actions),
        scan_config=scan_config,
    )


async def _load_scan(scan_id: str, db: AsyncSession) -> ScanTask:
    result = await db.execute(select(ScanTask).where(ScanTask.id == scan_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise AppException(404, "Scan not found")
    return task


def _retest_runtime_vars(
    value: Any,
    *,
    source_scan_id: str,
    source_result_ids: list[str],
    retest_reason: str,
    retest_type: str,
) -> dict[str, Any]:
    runtime_vars = dict(value) if isinstance(value, dict) else {}
    runtime_vars["autotest_retest"] = {
        "source_scan_id": source_scan_id,
        "source_result_ids": list(source_result_ids),
        "retest_reason": retest_reason,
        "retest_type": retest_type,
    }
    return runtime_vars


def _target_config(value: Any) -> TargetConfig | None:
    if not isinstance(value, dict):
        return None
    return TargetConfig(**value)


def _quartet_retest_advanced(value: Any) -> AdvancedConfig:
    original = value if isinstance(value, dict) else {}
    parallel_attacks = original.get("parallel_attacks")
    if not isinstance(parallel_attacks, int) or isinstance(parallel_attacks, bool):
        parallel_attacks = 2
    parallel_attacks = min(max(parallel_attacks, 1), 4)

    return AdvancedConfig(
        enable_crescendo=False,
        enable_tap=False,
        enable_pair=False,
        enable_self_explanation=False,
        enable_mutations=False,
        quartet_mode="full",
        parallel_attacks=parallel_attacks,
        mutation_strategies=[],
    )


def _dedupe(values: list[str] | tuple[str, ...] | Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
