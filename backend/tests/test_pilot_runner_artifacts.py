from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pilot_runner import prepare_pilot_run
from app.services.quartet_generator import load_suite

pytestmark = pytest.mark.anyio


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def test_dry_run_writes_config_suite_and_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "run_001"

    result = await prepare_pilot_run(
        output_dir=output_dir,
        case_count=30,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=True,
    )

    assert result.scan_task_id is None
    assert result.selected_case_count == 30
    assert result.planned_variant_count == 120
    assert (output_dir / "config.json").exists()
    assert (output_dir / "suite.json").exists()
    assert (output_dir / "summary.json").exists()

    suite = load_suite(output_dir / "suite.json")
    assert suite.manifest.content_hash == result.suite_hash
    assert suite.manifest.case_count == 30

    config = _read_json(output_dir / "config.json")
    assert config["run_id"] == "run_001"
    assert config["dry_run"] is True
    assert config["selected_case_count"] == 30
    assert config["planned_variant_count"] == 120
    assert config["suite_hash"] == result.suite_hash

    summary = _read_json(output_dir / "summary.json")
    assert summary["planned_variant_count"] == summary["selected_case_count"] * 4
    assert summary["scan_task_id"] is None
    assert "Stage 1.4" in summary["next_step"]


async def test_dry_run_does_not_open_database(tmp_path: Path) -> None:
    def forbidden_session_factory():
        raise AssertionError("dry-run must not open the database")

    result = await prepare_pilot_run(
        output_dir=tmp_path / "dry_run_no_db",
        case_count=6,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=True,
        session_factory=forbidden_session_factory,
    )

    assert result.selected_case_count == 6
    assert result.planned_variant_count == 24
