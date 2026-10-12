"""Regression coverage for scheduler cancellation, scan races and model routing."""
import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.scans import cancel_scan
from app.config import settings
from app.core.exceptions import AppException
from app.database import Base
from app.models import ScanTask
from app.models import AttackResult
from app.models.model_provider import ModelProvider
from app.services import llm_client, llm_scheduler, scan_runner
from app.services.scan_recovery import finalize_stuck_scan_from_db

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("scheduler_path", ["fixed", "rotation"])
async def test_outer_timeout_must_release_scheduler_slot(monkeypatch, scheduler_path):
    async def hanging_provider(*args, **kwargs):
        await asyncio.Event().wait()

    controller = llm_scheduler.AIMDController()
    info = llm_client.ProviderClientInfo("openai", "synthetic-audit-key")
    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    monkeypatch.setattr(settings, "llm_request_timeout_s", 10)
    monkeypatch.setattr(llm_client, "_call_openai_compatible", hanging_provider)
    if scheduler_path == "fixed":
        call = llm_scheduler.schedule_fixed_call(info, "fixture-model", [])
    else:
        pool = llm_scheduler.ProviderPool(controller)
        pool.add_slot(llm_scheduler.ProviderSlot(
            provider_info=info, model="fixture-model", key_id="synthetic-slot",
            role="generation", provider_id="fixture-provider",
        ))
        monkeypatch.setattr(llm_scheduler, "_pool", pool)
        call = llm_scheduler.schedule_call("generation", [])
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(call, timeout=0.03)
    assert sum(bucket["in_flight"] for bucket in controller.stats().values()) == 0


@pytest.mark.parametrize("scheduler_path", ["fixed", "rotation"])
async def test_cancellation_during_retry_backoff_does_not_double_release(monkeypatch, scheduler_path):
    attempted = asyncio.Event()

    async def rate_limited(*args, **kwargs):
        attempted.set()
        raise llm_client.LLMRateLimitError("controlled throttling", retry_after_s=60)

    controller = llm_scheduler.AIMDController()
    info = llm_client.ProviderClientInfo("openai", "synthetic-audit-key")
    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    monkeypatch.setattr(llm_scheduler, "_retry_bucket", llm_scheduler.RETRY_BUCKET_MAX)
    monkeypatch.setattr(llm_scheduler, "call_chat", rate_limited)
    if scheduler_path == "fixed":
        call = llm_scheduler.schedule_fixed_call(info, "fixture-model", [])
    else:
        pool = llm_scheduler.ProviderPool(controller)
        pool.add_slot(llm_scheduler.ProviderSlot(
            provider_info=info, model="fixture-model", key_id="synthetic-slot",
            role="generation", provider_id="fixture-provider",
        ))
        monkeypatch.setattr(llm_scheduler, "_pool", pool)
        call = llm_scheduler.schedule_call("generation", [])
    task = asyncio.create_task(call)
    await attempted.wait()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sum(bucket["in_flight"] for bucket in controller.stats().values()) == 0


async def test_postprocessing_error_does_not_release_a_successful_slot_twice(monkeypatch):
    controller = llm_scheduler.AIMDController()
    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    monkeypatch.setattr(llm_scheduler, "call_chat", AsyncMock(return_value="ok"))

    def broken_cache(*args):
        raise RuntimeError("controlled cache error")

    monkeypatch.setattr(llm_scheduler, "_store_dedup", broken_cache)
    with pytest.raises(RuntimeError, match="controlled cache error"):
        await llm_scheduler.schedule_fixed_call(llm_client.ProviderClientInfo("openai", "synthetic-key"), "fixture-model", [])
    assert sum(bucket["in_flight"] for bucket in controller.stats().values()) == 0


async def test_cancelled_waiter_does_not_release_another_calls_slot(monkeypatch):
    controller = llm_scheduler.AIMDController()
    info = llm_client.ProviderClientInfo("openai", "synthetic-key")
    key = llm_scheduler._slot_key_id(info.provider_type, info.api_key)
    bucket = controller._get(key)
    bucket.limit = 1
    await controller.acquire(key)
    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    call = AsyncMock(return_value="must not be called")
    monkeypatch.setattr(llm_scheduler, "call_chat", call)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(llm_scheduler.schedule_fixed_call(info, "fixture", []), 0.03)
    assert bucket.in_flight == 1
    call.assert_not_called()
    await controller.release_on_error(key)


async def test_repeated_cancellation_still_finishes_slot_cleanup(monkeypatch):
    controller = llm_scheduler.AIMDController()
    info = llm_client.ProviderClientInfo("openai", "synthetic-key")
    key = llm_scheduler._slot_key_id(info.provider_type, info.api_key)
    entered = asyncio.Event()

    async def hang(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    monkeypatch.setattr(llm_scheduler, "call_chat", hang)
    task = asyncio.create_task(llm_scheduler.schedule_fixed_call(info, "fixture", []))
    await entered.wait()
    bucket = controller._get(key)
    await bucket._lock.acquire()
    try:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        bucket._lock.release()
    for _ in range(10):
        await asyncio.sleep(0)
        if bucket.in_flight == 0:
            break
    assert bucket.in_flight == 0


@pytest.mark.parametrize("role", ["judge", "generation"])
async def test_recorded_model_without_provider_id_is_used(monkeypatch, role):
    info = llm_client.ProviderClientInfo("openai", "synthetic-default-key")
    monkeypatch.setattr(llm_client, f"_{role}_provider_cache", (time.monotonic() + 60, (info, "changed-default-model")))
    id_var = getattr(llm_client, f"_scan_{role}_provider_id")
    model_var = getattr(llm_client, f"_scan_{role}_model")
    id_token = id_var.set(None)
    model_token = model_var.set("recorded-original-model")
    try:
        _, actual = await getattr(llm_client, f"get_{role}_provider")()
        assert actual == "recorded-original-model"
    finally:
        id_var.reset(id_token)
        model_var.reset(model_token)


@pytest.mark.parametrize("role", ["judge", "generation"])
@pytest.mark.parametrize("default_source", ["database", "platform"])
async def test_cold_model_override_does_not_pollute_default_cache(monkeypatch, db_engine, role, default_source):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    if default_source == "database":
        async with factory() as db:
            db.add(ModelProvider(
                name="fixture default", provider_type="custom", api_key="synthetic-provider-key",
                base_url="https://fixture.example.com/v1", judge_model="default-judge",
                mini_model="default-generation", enabled=True, is_judge_default=True,
                is_generation_default=True,
            ))
            await db.commit()
    monkeypatch.setattr("app.database.async_session", factory)
    monkeypatch.setattr(settings, "openai_model", "default-judge")
    monkeypatch.setattr(settings, "openai_mini_model", "default-generation")
    monkeypatch.setattr(llm_client, f"_{role}_provider_cache", None)
    id_var = getattr(llm_client, f"_scan_{role}_provider_id")
    model_var = getattr(llm_client, f"_scan_{role}_model")
    id_token, model_token = id_var.set(None), model_var.set("recorded-original-model")
    try:
        _, actual = await getattr(llm_client, f"get_{role}_provider")()
        assert actual == "recorded-original-model"
        model_var.set(None)
        _, default = await getattr(llm_client, f"get_{role}_provider")()
        assert default == f"default-{role}"
    finally:
        id_var.reset(id_token)
        model_var.reset(model_token)


@pytest.mark.parametrize("role", ["judge", "generation"])
async def test_missing_explicit_provider_never_silently_falls_back(monkeypatch, role):
    monkeypatch.setattr(llm_client, "get_provider_by_id", AsyncMock(return_value=None))
    info = llm_client.ProviderClientInfo("openai", "synthetic-default-key")
    monkeypatch.setattr(llm_client, f"_{role}_provider_cache", (time.monotonic() + 60, (info, "other-default")))
    variable = getattr(llm_client, f"_scan_{role}_provider_id")
    token = variable.set("disabled-fixture-provider")
    try:
        with pytest.raises(llm_client.LLMConfigurationError):
            await getattr(llm_client, f"get_{role}_provider")()
    finally:
        variable.reset(token)


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + (tmp_path / "race.db").as_posix())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def create_task(factory):
    async with factory() as db:
        task = ScanTask(name="audit cancellation fixture", target_url="https://fixture.example.com", status="pending")
        db.add(task)
        await db.commit()
        return task.id


def no_network_runner(monkeypatch):
    monkeypatch.setattr(scan_runner.AttackEngine, "get_all_templates", lambda *args: [])
    monkeypatch.setattr(scan_runner, "probe_target_health", AsyncMock(return_value={"target_health": "healthy"}))


async def test_cancel_between_startup_read_and_write_is_not_overwritten(monkeypatch, db_engine):
    normal = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(normal)
    loaded = asyncio.Event()
    allow_startup_to_continue = asyncio.Event()
    gated = False

    class GatedSession(AsyncSession):
        async def execute(self, *args, **kwargs):
            nonlocal gated
            result = await super().execute(*args, **kwargs)
            if not gated:
                gated = True
                loaded.set()
                await allow_startup_to_continue.wait()
            return result

    monkeypatch.setattr(scan_runner, "async_session", async_sessionmaker(db_engine, class_=GatedSession, expire_on_commit=False))
    no_network_runner(monkeypatch)
    runner = asyncio.create_task(scan_runner.run_scan(task_id, {}))
    await asyncio.wait_for(loaded.wait(), 2)
    try:
        async with normal() as db:
            await asyncio.wait_for(cancel_scan(task_id, db), 2)
    finally:
        allow_startup_to_continue.set()
    await asyncio.wait_for(runner, 3)
    async with normal() as db:
        stored = await db.get(ScanTask, task_id)
        assert stored.status == "cancelled"


async def test_exception_after_user_cancel_preserves_cancelled(monkeypatch, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(factory)
    monkeypatch.setattr(scan_runner, "async_session", factory)
    no_network_runner(monkeypatch)

    async def cancel_then_fail(task):
        async with factory() as db:
            await cancel_scan(task_id, db)
        raise RuntimeError("controlled failure after cancellation")

    monkeypatch.setattr(scan_runner, "probe_target_health", cancel_then_fail)
    socket = AsyncMock()
    await scan_runner.run_scan(task_id, {task_id: [socket]})
    async with factory() as db:
        stored = await db.get(ScanTask, task_id)
        assert stored.status == "cancelled"
    assert socket.send_json.call_args_list[-1].args[0]["type"] == "scan_cancelled"


async def test_cancel_during_finalization_is_not_overwritten(monkeypatch, db_engine):
    normal = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(normal)
    final_read = asyncio.Event()
    release = asyncio.Event()

    class GatedFinalizationSession(AsyncSession):
        async def refresh(self, instance, attribute_names=None, **kwargs):
            await super().refresh(instance, attribute_names=attribute_names, **kwargs)
            if attribute_names and "completed_attacks" in attribute_names and not final_read.is_set():
                final_read.set()
                await release.wait()

    monkeypatch.setattr(scan_runner, "async_session", async_sessionmaker(db_engine, class_=GatedFinalizationSession, expire_on_commit=False))
    no_network_runner(monkeypatch)
    runner = asyncio.create_task(scan_runner.run_scan(task_id, {}))
    await asyncio.wait_for(final_read.wait(), 2)
    try:
        async with normal() as db:
            await cancel_scan(task_id, db)
    finally:
        release.set()
    await asyncio.wait_for(runner, 3)
    async with normal() as db:
        assert (await db.get(ScanTask, task_id)).status == "cancelled"


async def test_cancel_api_cannot_overwrite_a_completed_task(db_engine):
    normal = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(normal)
    loaded, release = asyncio.Event(), asyncio.Event()

    class GatedCancelSession(AsyncSession):
        async def execute(self, *args, **kwargs):
            result = await super().execute(*args, **kwargs)
            if not loaded.is_set():
                loaded.set()
                await release.wait()
            return result

    factory = async_sessionmaker(db_engine, class_=GatedCancelSession, expire_on_commit=False)
    async with factory() as cancel_db:
        cancellation = asyncio.create_task(cancel_scan(task_id, cancel_db))
        await asyncio.wait_for(loaded.wait(), 2)
        async with normal() as db:
            task = await db.get(ScanTask, task_id)
            task.status = "completed"
            await db.commit()
        release.set()
        with pytest.raises(AppException):
            await cancellation
    async with normal() as db:
        assert (await db.get(ScanTask, task_id)).status == "completed"


async def test_recovery_cannot_overwrite_concurrent_cancel(db_engine):
    normal = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(normal)
    async with normal() as db:
        task = await db.get(ScanTask, task_id)
        task.status = "running"
        task.total_attacks = task.completed_attacks = 1
        db.add(AttackResult(
            scan_task_id=task_id, template_id="fixture", category="prompt_injection",
            technique="fixture", attack_name="fixture", payload_text="fixture",
            target_response="fixture response", attack_successful=False, risk_score=0,
        ))
        await db.commit()
    loaded, release = asyncio.Event(), asyncio.Event()

    class GatedRecoverySession(AsyncSession):
        async def execute(self, *args, **kwargs):
            result = await super().execute(*args, **kwargs)
            if not loaded.is_set():
                loaded.set()
                await release.wait()
            return result

    factory = async_sessionmaker(db_engine, class_=GatedRecoverySession, expire_on_commit=False)
    async with factory() as recovery_db:
        recovery = asyncio.create_task(finalize_stuck_scan_from_db(task_id, recovery_db))
        await asyncio.wait_for(loaded.wait(), 2)
        async with normal() as db:
            await cancel_scan(task_id, db)
        release.set()
        assert (await recovery)["status"] == "cancelled"


@pytest.mark.parametrize("configured_model", [None, "task-model"])
async def test_scan_routing_is_scoped_and_restored(monkeypatch, db_engine, configured_model):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    task_id = await create_task(factory)
    async with factory() as db:
        task = await db.get(ScanTask, task_id)
        task.judge_model = configured_model
        await db.commit()
    monkeypatch.setattr(scan_runner, "async_session", factory)
    no_network_runner(monkeypatch)
    observed = []

    async def observe(task):
        observed.append(llm_client._scan_judge_model.get())
        return {"target_health": "healthy"}

    monkeypatch.setattr(scan_runner, "probe_target_health", observe)
    token = llm_client._scan_judge_model.set("outer-scope-model")
    try:
        await scan_runner.run_scan(task_id, {})
        assert observed == [configured_model]
        assert llm_client._scan_judge_model.get() == "outer-scope-model"
    finally:
        llm_client._scan_judge_model.reset(token)
