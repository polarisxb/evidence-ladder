from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.database import async_session, init_db
from app.models import ScanTask
from app.services.pilot_runner import prepare_pilot_run

pytestmark = pytest.mark.anyio


async def test_prepare_mode_creates_pending_scan_task(tmp_path: Path) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_run",
        case_count=6,
        model="gpt-4o-mini",
        target_type="builtin_vulnerable",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    assert result.scan_task_id is not None

    async with async_session() as db:
        task = (
            await db.execute(select(ScanTask).where(ScanTask.id == result.scan_task_id))
        ).scalar_one()

    assert task.status == "pending"
    assert task.name == "Pilot v0.1 prepared_run"
    assert task.target_type == "builtin_vulnerable"
    assert task.target_url == "builtin"
    assert task.attack_categories == [
        "prompt_injection",
        "system_prompt_extraction",
        "jailbreak",
        "information_disclosure",
        "indirect_injection",
        "excessive_agency",
    ]
    assert task.started_at is None
    assert task.completed_at is None
    assert task.advanced_config["quartet_mode"] == "full"
    assert task.advanced_config["pilot_run_id"] == "prepared_run"
    assert task.advanced_config["pilot_suite_hash"] == result.suite_hash
    assert task.advanced_config["pilot_case_count"] == 6
    assert task.advanced_config["pilot_variant_count"] == 24
    assert task.advanced_config["pilot_seed"] == 20260504
    assert task.advanced_config["pilot_model"] == "gpt-4o-mini"


async def test_prepare_openai_compatible_task_uses_platform_default_target(
    tmp_path: Path,
) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_openai",
        case_count=6,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    assert result.scan_task_id is not None

    async with async_session() as db:
        task = (
            await db.execute(select(ScanTask).where(ScanTask.id == result.scan_task_id))
        ).scalar_one()

    assert task.target_type == "openai_compatible"
    assert task.target_url == "default"
    assert task.target_config == {"model": "gpt-4o-mini"}
    assert task.advanced_config["pilot_model"] == "gpt-4o-mini"


async def test_prepare_mode_updates_artifacts_with_scan_task_id(tmp_path: Path) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_artifacts",
        case_count=6,
        model="gpt-4o-mini",
        target_type="builtin_vulnerable",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    config = result.config_path.read_text(encoding="utf-8")
    summary = result.summary_path.read_text(encoding="utf-8")
    assert result.scan_task_id is not None
    assert result.scan_task_id in config
    assert result.scan_task_id in summary


async def test_prepare_rejects_custom_and_adapter_targets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not supported"):
        await prepare_pilot_run(
            output_dir=tmp_path / "custom",
            target_type="custom",
            dry_run=True,
        )

    with pytest.raises(ValueError, match="not supported"):
        await prepare_pilot_run(
            output_dir=tmp_path / "adapter",
            target_type="adapter",
            dry_run=True,
        )
