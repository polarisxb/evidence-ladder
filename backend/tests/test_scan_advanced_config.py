"""Advanced scan options must survive scan creation and reach the runner.

The New Scan page sends health-detection thresholds and the in-scan retest arm
inside ``advanced``. ``AdvancedConfig`` used to drop both silently (Pydantic
ignores undeclared fields), so the inputs had no effect and the conflict-driven
retest loop could not be switched on through the API at all.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.database import async_session
from app.main import app
from app.models import ScanTask
from app.schemas.scan import AdvancedConfig
from app.services.retest_orchestrator import resolve_retest_arm
from app.services.scan_runner import _new_scan_health_tracker

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    async def noop_run_scan(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_builtin_scan(client: AsyncClient, advanced: dict) -> ScanTask:
    resp = await client.post("/api/v1/scans", json={
        "name": "advanced config fixture",
        "target_type": "builtin_vulnerable",
        "target_url": "builtin",
        "target_config": {"vulnerable_level": 1},
        "attack_categories": ["jailbreak"],
        "advanced": advanced,
    })
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["data"]["task_id"]
    async with async_session() as db:
        return (await db.execute(select(ScanTask).where(ScanTask.id == task_id))).scalar_one()


def test_schema_keeps_health_and_retest_fields() -> None:
    advanced = AdvancedConfig(
        health_window_size=20,
        health_invalid_threshold=12,
        health_signature_streak=4,
        health_unhealthy_streak=30,
        health_recovery_streak=2,
        retest_arm="B",
        max_retest_rounds=3,
    )

    assert advanced.model_dump(exclude_none=True, exclude_unset=True) == {
        "health_window_size": 20,
        "health_invalid_threshold": 12,
        "health_signature_streak": 4,
        "health_unhealthy_streak": 30,
        "health_recovery_streak": 2,
        "retest_arm": "B",
        "max_retest_rounds": 3,
    }


@pytest.mark.parametrize("field,value", [
    ("health_window_size", 1),
    ("health_invalid_threshold", 0),
    ("health_signature_streak", 101),
    ("max_retest_rounds", 0),
    ("max_retest_rounds", 6),
    ("retest_arm", "C"),
])
def test_schema_rejects_out_of_range_values(field: str, value) -> None:
    with pytest.raises(ValidationError):
        AdvancedConfig(**{field: value})


def test_invalid_threshold_cannot_exceed_window() -> None:
    with pytest.raises(ValidationError, match="cannot exceed health_window_size"):
        AdvancedConfig(health_window_size=5, health_invalid_threshold=6)


async def test_health_thresholds_reach_the_runner_tracker(client: AsyncClient) -> None:
    task = await _create_builtin_scan(client, {
        "health_window_size": 20,
        "health_invalid_threshold": 12,
        "health_signature_streak": 4,
    })

    assert task.advanced_config["health_window_size"] == 20
    tracker = _new_scan_health_tracker(task.advanced_config)
    assert tracker["window_size"] == 20
    assert tracker["recent_invalid_window"].maxlen == 20
    assert tracker["invalid_threshold"] == 12
    assert tracker["signature_streak_threshold"] == 4


async def test_retest_arm_b_turns_on_the_in_scan_retest_loop(client: AsyncClient) -> None:
    task = await _create_builtin_scan(client, {"retest_arm": "B", "max_retest_rounds": 3})

    resolved = resolve_retest_arm(task.advanced_config, target_type=task.target_type)
    assert resolved is not None
    arm, config = resolved
    assert arm == "B"
    assert config.max_retest_rounds == 3
    assert config.quartet_enabled is True
    assert config.probe_available is False  # builtin target has no business probe


async def test_retest_arm_a_records_lineage_without_retest(client: AsyncClient) -> None:
    task = await _create_builtin_scan(client, {"retest_arm": "A"})

    arm, config = resolve_retest_arm(task.advanced_config, target_type=task.target_type)
    assert arm == "A"
    assert config.max_retest_rounds == 0


async def test_retest_stays_off_when_not_requested(client: AsyncClient) -> None:
    task = await _create_builtin_scan(client, {"enable_pair": True})

    assert "retest_arm" not in task.advanced_config
    assert resolve_retest_arm(task.advanced_config, target_type=task.target_type) is None


async def test_api_rejects_unknown_retest_arm(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/scans", json={
        "target_type": "builtin_vulnerable",
        "target_url": "builtin",
        "advanced": {"retest_arm": "C"},
    })
    assert resp.status_code == 422
