# backend/app/tests/test_retest_loop/test_real_executor_loop.py
"""Integration: drive RealRetestExecutor through run_retest_loop_async."""
import asyncio
import types

from app.services import retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor
from app.services.retest_loop import run_retest_loop_async
from app.services.retest_policy import RetestConfig

ARM_B = RetestConfig(max_retest_rounds=2, quartet_enabled=True,
                     canary_enabled=False, probe_available=True)


class _FakeProbeResponse:
    def __init__(self, *, verified, failure_type=None, steps=1):
        self.verified = verified
        self.failure_type = failure_type
        self.step_results = [object()] * steps


def _task():
    return types.SimpleNamespace(id="scan1", runtime_vars={}, target_type="adapter",
                                 target_config={},
                                 _resolved_adapter_payload={"enabled": True,
                                                            "probe_config": {"enabled": True}})


def test_real_probe_upgrades_text_claim_to_confirmed(monkeypatch):
    async def _fake_probe(adapter, **kwargs):
        return _FakeProbeResponse(verified=True)
    monkeypatch.setattr(rex, "execute_probe", _fake_probe)

    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1
    lineage = asyncio.run(run_retest_loop_async(result, RealRetestExecutor(_task()), ARM_B))

    assert lineage.final_verdict == "confirmed"
    assert lineage.final_evidence_level == "E5"
    assert lineage.total_extra_queries >= 1
    assert any("run_probe" in str(r.actions) for r in lineage.rounds)


def test_real_probe_failure_overturns_text_claim(monkeypatch):
    async def _fake_probe(adapter, **kwargs):
        return _FakeProbeResponse(verified=False, failure_type="assertion_failed")
    monkeypatch.setattr(rex, "execute_probe", _fake_probe)

    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1
    lineage = asyncio.run(run_retest_loop_async(result, RealRetestExecutor(_task()), ARM_B))

    assert lineage.final_verdict == "overturned"
    assert lineage.converged_reason == "overturned"
