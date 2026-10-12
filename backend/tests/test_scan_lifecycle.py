import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import scans
from app.database import Base
from app.models import AttackResult, ScanTask
from app.services import scan_recovery, scan_runner

pytestmark = pytest.mark.anyio


@pytest.fixture
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def create_task(db, *, status="running", total=2, count=1):
    task = ScanTask(
        name="lifecycle fixture", target_url="https://example.com", status=status,
        total_attacks=total, completed_attacks=count,
    )
    db.add(task)
    await db.flush()
    for index in range(count):
        db.add(AttackResult(
            scan_task_id=task.id, template_id=f"fixture-{index}", category="prompt_injection",
            technique="fixture", attack_name="fixture", payload_text="fixture",
            target_response="fixture response", attack_successful=False, risk_score=0,
        ))
    await db.commit()
    return task


async def test_pause_signals_before_finalizing(monkeypatch):
    event = asyncio.Event()
    monkeypatch.setitem(scan_runner._scan_stop_events, "pause-fixture", event)

    async def finalize(task_id, db):
        assert event.is_set(), "runner must receive stop before DB finalization"
        return {"status": "cancelled"}

    monkeypatch.setattr(scans, "finalize_stuck_scan_from_db", finalize)
    await scans.pause_scan("pause-fixture", db=AsyncMock())


@pytest.mark.parametrize("status,total,count,expected", [
    ("running", 2, 1, "cancelled"),
    ("pending", 2, 0, "cancelled"),
    ("running", 0, 0, "cancelled"),
    ("cancelled", 2, 1, "cancelled"),
    ("failed", 2, 1, "failed"),
    ("cancelled", 1, 1, "cancelled"),
    ("failed", 1, 1, "failed"),
    ("running", 1, 1, "completed"),
])
async def test_recovery_preserves_honest_terminal_status(sessions, status, total, count, expected):
    async with sessions() as db:
        task = await create_task(db, status=status, total=total, count=count)
        result = await scan_recovery.finalize_stuck_scan_from_db(task.id, db)
        await db.refresh(task)
        assert result["status"] == task.status == expected
        assert task.completed_attacks == count
        assert task.completed_at is not None
        if not count:
            assert task.overall_score is None


async def test_runner_broadcasts_cancelled_with_progress(sessions, monkeypatch):
    async with sessions() as db:
        task = await create_task(db, status="pending")
    monkeypatch.setattr(scan_runner, "async_session", sessions)
    monkeypatch.setattr(scan_runner.AttackEngine, "get_all_templates", lambda *args: [{
        "id": "fixture", "payloads": [{"text": "one"}, {"text": "two"}],
    }])
    monkeypatch.setattr(scan_runner, "probe_target_health", AsyncMock(return_value={
        "target_health": "healthy", "health_probe_passed": True,
    }))

    async def cancel_during_run(*args, **kwargs):
        async with sessions() as db:
            await scans.cancel_scan(task.id, db)
        assert scan_runner._scan_stop_events[task.id].is_set()

    monkeypatch.setattr(scan_runner, "_run_base_templates", cancel_during_run)
    socket = AsyncMock()
    await scan_runner.run_scan(task.id, {task.id: [socket]})
    events = [call.args[0] for call in socket.send_json.call_args_list]
    terminal = [e for e in events if e["type"] in {"scan_completed", "scan_failed", "scan_cancelled"}]
    assert len(terminal) == 1
    assert terminal[0]["type"] == "scan_cancelled"
    assert terminal[0]["completed"] == 1
    assert terminal[0]["total"] == 2
    assert terminal[0]["target_health"] == "healthy"
    async with sessions() as db:
        assert (await db.get(ScanTask, task.id)).status == "cancelled"


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
@pytest.mark.parametrize("overrides", [True, False])
async def test_retry_preserves_judge_and_generation_routing(sessions, status, overrides):
    fields = {
        "judge_provider_id": "fixture-judge", "judge_model": "fixture-judge-model",
        "generation_provider_id": "fixture-generator", "generation_model": "fixture-generation-model",
    }
    async with sessions() as db:
        original = await create_task(db, status=status)
        for key, value in fields.items():
            setattr(original, key, value if overrides else None)
        await db.commit()
        background = BackgroundTasks()
        response = await scans.retry_scan(original.id, background, db)
        retry = await db.get(ScanTask, response["data"]["task_id"])
        assert retry.id != original.id
        for key, value in fields.items():
            assert getattr(retry, key) == (value if overrides else None)
        assert retry.status == "pending"
        assert original.status == status
        assert len(background.tasks) == 1
        assert background.tasks[0].args[0] == retry.id


async def test_pause_before_runner_start_does_not_restart_scan(sessions, monkeypatch):
    async with sessions() as db:
        task = await create_task(db, status="pending", count=0)
        await scans.pause_scan(task.id, db)
    monkeypatch.setattr(scan_runner, "async_session", sessions)
    templates = Mock(return_value=[])
    monkeypatch.setattr(scan_runner.AttackEngine, "get_all_templates", templates)
    probe = AsyncMock(return_value={"target_health": "healthy"})
    monkeypatch.setattr(scan_runner, "probe_target_health", probe)
    socket = AsyncMock()
    await scan_runner.run_scan(task.id, {task.id: [socket]})
    async with sessions() as db:
        assert (await db.get(ScanTask, task.id)).status == "cancelled"
    templates.assert_not_called()
    probe.assert_not_called()
    events = [call.args[0] for call in socket.send_json.call_args_list]
    assert [e["type"] for e in events] == ["scan_cancelled"]
    assert events[0]["completed"] == 0
