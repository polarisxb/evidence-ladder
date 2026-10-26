"""The scan API says whether a pending/running scan still has a runner.

After a backend restart, pending/running rows keep their status but nothing
executes them; the progress page used to show "scanning" forever.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import async_session
from app.main import app
from app.models import ScanTask
from app.services import scan_runner

pytestmark = pytest.mark.anyio

FIXTURE_NAME = "liveness-fixture"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with async_session() as db:
        await db.execute(delete(ScanTask).where(ScanTask.name == FIXTURE_NAME))
        await db.commit()


async def _scan(status: str) -> str:
    async with async_session() as db:
        task = ScanTask(name=FIXTURE_NAME, target_url="builtin", target_type="builtin_vulnerable", status=status)
        db.add(task)
        await db.commit()
        return task.id


async def test_orphaned_pending_scan_reports_no_runner(client: AsyncClient) -> None:
    task_id = await _scan("pending")

    body = (await client.get(f"/api/v1/scans/{task_id}")).json()["data"]

    assert body["status"] == "pending"
    assert body["runner_active"] is False


async def test_scan_with_a_runner_reports_it(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    task_id = await _scan("running")
    monkeypatch.setattr(scan_runner, "_active_scan_ids", {task_id})

    body = (await client.get(f"/api/v1/scans/{task_id}")).json()["data"]
    listed = (await client.get("/api/v1/scans", params={"q": FIXTURE_NAME})).json()["data"]

    assert body["runner_active"] is True
    assert [item["runner_active"] for item in listed if item["id"] == task_id] == [True]


async def test_finished_scan_has_no_liveness_value(client: AsyncClient) -> None:
    task_id = await _scan("completed")

    body = (await client.get(f"/api/v1/scans/{task_id}")).json()["data"]

    assert body["runner_active"] is None


async def test_runner_registers_itself_only_while_running(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []

    async def fake_run(task_id, ws_clients):
        seen.append(scan_runner.is_scan_runner_active(task_id))

    monkeypatch.setattr(scan_runner, "_run_scan", fake_run)
    await scan_runner.run_scan("liveness-task", {})

    assert seen == [True]
    assert scan_runner.is_scan_runner_active("liveness-task") is False
