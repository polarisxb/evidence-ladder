from __future__ import annotations

from pathlib import Path

from app.scripts import run_pilot


def test_cli_dry_run_writes_artifacts_and_prints_summary(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "cli_run"

    run_pilot.main([
        "--cases",
        "6",
        "--model",
        "gpt-4o-mini",
        "--target-type",
        "openai_compatible",
        "--output-dir",
        str(output_dir),
        "--seed",
        "20260504",
        "--dry-run",
    ])

    captured = capsys.readouterr().out
    assert "run_id=cli_run" in captured
    assert "selected_cases=6" in captured
    assert "planned_variants=24" in captured
    assert "scan_task_id=None" in captured
    assert (output_dir / "config.json").exists()
    assert (output_dir / "suite.json").exists()
    assert (output_dir / "summary.json").exists()
