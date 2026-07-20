# backend/app/tests/test_retest_loop/test_real_executor_probe.py
import asyncio
import types

from app.services import retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor


class _FakeProbeResponse:
    def __init__(self, *, verified, failure_type=None, steps=1):
        self.verified = verified
        self.failure_type = failure_type
        self.step_results = [object()] * steps


def _task():
    return types.SimpleNamespace(
        id="scan1",
        runtime_vars={},
        target_type="adapter",
        _resolved_adapter_payload={"enabled": True, "probe_config": {"enabled": True}},
    )


def _patch_probe(monkeypatch, response):
    async def _fake_execute_probe(adapter, **kwargs):
        return response
    monkeypatch.setattr(rex, "execute_probe", _fake_execute_probe)


def test_run_probe_verified_maps_to_probe_verified(monkeypatch):
    _patch_probe(monkeypatch, _FakeProbeResponse(verified=True, steps=2))
    executor = RealRetestExecutor(_task())
    delta = asyncio.run(executor.run_probe({"case_id": "c1"}))
    assert delta.action_type == "run_probe"
    assert delta.evidence_updates == {"business_verification_status": "probe_verified"}
    assert delta.contradiction is False  # arbiter derives contradictions, not the executor
    assert delta.extra_queries == 2


def test_run_probe_failed_maps_to_probe_failed(monkeypatch):
    _patch_probe(monkeypatch, _FakeProbeResponse(verified=False, failure_type="assertion_failed"))
    delta = asyncio.run(RealRetestExecutor(_task()).run_probe({"case_id": "c1"}))
    assert delta.evidence_updates == {"business_verification_status": "probe_failed"}
    assert delta.contradiction is False


def test_run_probe_transport_failure_is_inconclusive(monkeypatch):
    _patch_probe(monkeypatch, _FakeProbeResponse(verified=False, failure_type="timeout"))
    delta = asyncio.run(RealRetestExecutor(_task()).run_probe({"case_id": "c1"}))
    assert delta.evidence_updates == {"business_verification_status": "probe_inconclusive"}


def test_run_probe_without_probe_config_is_noop():
    task = types.SimpleNamespace(id="s", runtime_vars={}, target_type="adapter",
                                 _resolved_adapter_payload={"enabled": True})
    delta = asyncio.run(RealRetestExecutor(task).run_probe({"case_id": "c1"}))
    assert delta.evidence_updates == {}
    assert delta.extra_queries == 0


def test_provider_stateful_sandbox_uses_separate_builtin_probe_channel():
    task = types.SimpleNamespace(
        id="provider-sandbox",
        runtime_vars={},
        target_type="openai_compatible",
        target_config={
            "stateful_sandbox_config": {
                "enabled": True,
                "commit_policy": "never",
            },
            "builtin_probe_config": {
                "enabled": True,
                "state_key": "account-42-role-admin",
            },
        },
    )

    payload = RealRetestExecutor(task)._resolved_probe_payload()

    assert payload == {
        "enabled": True,
        "mode": "builtin_vulnerable",
        "probe_config": {
            "enabled": True,
            "state_key": "account-42-role-admin",
        },
    }


def test_run_probe_execute_probe_exception_is_inconclusive(monkeypatch):
    async def _boom(adapter, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(rex, "execute_probe", _boom)
    delta = asyncio.run(RealRetestExecutor(_task()).run_probe({"case_id": "c1"}))
    assert delta.evidence_updates == {"business_verification_status": "probe_inconclusive"}
