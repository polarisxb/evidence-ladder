# backend/app/tests/test_retest_loop/test_real_executor_loop.py
"""Integration: drive RealRetestExecutor through run_retest_loop_async."""

import asyncio
import types

from app.services import case_executor, retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor
from app.services.retest_loop import run_retest_loop_async
from app.services.retest_policy import RetestConfig

ARM_B = RetestConfig(
    max_retest_rounds=2,
    quartet_enabled=True,
    canary_enabled=False,
    probe_available=True,
)


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
        target_config={},
        _resolved_adapter_payload={"enabled": True, "probe_config": {"enabled": True}},
    )


def test_real_probe_upgrades_text_claim_to_confirmed(monkeypatch):
    async def _fake_probe(adapter, **kwargs):
        return _FakeProbeResponse(verified=True)

    monkeypatch.setattr(rex, "execute_probe", _fake_probe)

    result = {
        "case_id": "c1",
        "behavior_flags": {"unauthorized_action_claim": True},
    }  # E1
    lineage = asyncio.run(
        run_retest_loop_async(result, RealRetestExecutor(_task()), ARM_B)
    )

    assert lineage.final_verdict == "confirmed"
    assert lineage.final_evidence_level == "E5"
    assert lineage.total_extra_queries >= 1
    assert any("run_probe" in str(r.actions) for r in lineage.rounds)


def test_real_probe_failure_overturns_text_claim(monkeypatch):
    async def _fake_probe(adapter, **kwargs):
        return _FakeProbeResponse(verified=False, failure_type="assertion_failed")

    monkeypatch.setattr(rex, "execute_probe", _fake_probe)

    result = {
        "case_id": "c1",
        "behavior_flags": {"unauthorized_action_claim": True},
    }  # E1
    lineage = asyncio.run(
        run_retest_loop_async(result, RealRetestExecutor(_task()), ARM_B)
    )

    assert lineage.final_verdict == "overturned"
    assert lineage.converged_reason == "overturned"


def test_text_claim_without_executable_probe_is_not_evaluable():
    task = types.SimpleNamespace(
        id="scan1",
        runtime_vars={},
        target_type="adapter",
        target_config={},
        _resolved_adapter_payload={"enabled": True},
    )
    result = {
        "case_id": "c1",
        "behavior_flags": {"unauthorized_action_claim": True},
    }
    config = RetestConfig(
        max_retest_rounds=1,
        quartet_enabled=False,
        canary_enabled=False,
        probe_available=True,
    )

    lineage = asyncio.run(
        run_retest_loop_async(result, RealRetestExecutor(task), config)
    )

    assert lineage.final_verdict == "not_evaluable"
    assert lineage.converged_reason == "no_executable_action"
    assert lineage.total_extra_queries == 0
    assert lineage.rounds == []


def test_quartet_analyzer_exception_never_overturns(monkeypatch):
    async def _fake_execute(task, template, payload, **kwargs):
        return [
            {
                "variant_type": variant,
                "is_primary": variant == "attack",
                "request_text": payload,
                "response_text": "ambiguous response",
                "response_status": "completed",
            }
            for variant in ("attack", "clean", "quoted_attack", "benign_distractor")
        ]

    async def _raise_analyzer_error(*args, **kwargs):
        raise RuntimeError("simulated pinned judge outage")

    monkeypatch.setattr(rex, "execute_case_variants", _fake_execute)
    monkeypatch.setattr(case_executor, "analyze_response", _raise_analyzer_error)

    result = {"case_id": "c1", "verdict_status": "ai_suspected"}
    config = RetestConfig(
        max_retest_rounds=1,
        quartet_enabled=True,
        canary_enabled=False,
        probe_available=False,
    )
    lineage = asyncio.run(
        run_retest_loop_async(
            result,
            RealRetestExecutor(
                _task(),
                judge_provider_id="pinned-judge-provider",
                judge_model_version="judge-snapshot-2026-07-01",
            ),
            config,
        )
    )

    assert lineage.final_verdict != "overturned"
    assert lineage.final_verdict in {"manual_review", "not_evaluable"}
