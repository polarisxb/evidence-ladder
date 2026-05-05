from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.scripts import execute_pilot


def test_execute_pilot_cli_requires_scan_task_id() -> None:
    with pytest.raises(SystemExit) as exc_info:
        execute_pilot.main([])

    assert exc_info.value.code == 2


def test_execute_pilot_cli_runs_scan_and_prints_summary(monkeypatch, capsys) -> None:
    calls: list[object] = []

    async def fake_init_db() -> None:
        calls.append("init_db")

    async def fake_run_scan(scan_task_id: str, ws_clients: dict) -> None:
        calls.append(("run_scan", scan_task_id, ws_clients))

    async def fake_load_scan_task(scan_task_id: str):
        calls.append(("load", scan_task_id))
        return SimpleNamespace(
            id=scan_task_id,
            status="completed",
            completed_attacks=30,
            total_attacks=30,
            vulnerabilities_found=4,
            overall_score=7.25,
        )

    monkeypatch.setattr(execute_pilot, "init_db", fake_init_db)
    monkeypatch.setattr(execute_pilot, "run_scan", fake_run_scan)
    monkeypatch.setattr(execute_pilot, "_load_scan_task", fake_load_scan_task)

    execute_pilot.main(["--scan-task-id", "scan-123"])

    assert calls == [
        "init_db",
        ("run_scan", "scan-123", {}),
        ("load", "scan-123"),
    ]
    captured = capsys.readouterr().out
    assert "scan_task_id=scan-123" in captured
    assert "status=completed" in captured
    assert "completed_attacks=30" in captured
    assert "total_attacks=30" in captured
    assert "vulnerabilities_found=4" in captured
    assert "overall_score=7.25" in captured
