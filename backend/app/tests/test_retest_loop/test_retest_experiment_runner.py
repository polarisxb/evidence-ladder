"""Task 2 — experiment runner over a frozen suite + cached initial responses.

Runs Arms A (judge-only), A' (re-judge) and B (④ retest) over the SAME cached
result per case and records each arm's verdict, evidence level, extra query cost
(from the lineage) and lineage.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor
from app.services.retest_experiment import (
    ArmOutcome,
    ExperimentCase,
    run_experiment_suite,
)
from app.services.retest_loop import EvidenceDelta

_ORDER = ["E0", "E1", "E2", "E3", "E4", "E5"]


def _idx(level: str | None) -> int:
    return _ORDER.index(level) if level in _ORDER else -1


class _StaticVerifier:
    def rejudge(self, result: dict[str, Any]) -> dict[str, Any]:
        return {"verdict_status": "ai_suspected"}


class _ProbeConfirmsExecutor:
    """Synthetic Arm-B executor: a probe re-execution confirms the claim (E5)."""

    def run_quartet(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(action_type="run_quartet")

    def run_canary(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(action_type="run_canary")

    def run_probe(self, result: dict[str, Any]) -> EvidenceDelta:
        return EvidenceDelta(
            action_type="run_probe",
            evidence_updates={"business_verification_status": "probe_verified"},
            extra_queries=1,
            extra_cost_ms=1200.0,
            summary="probe confirmed",
        )


def test_runner_records_three_arms_per_case() -> None:
    # Weak-but-true: E1 text-claim that a probe would confirm.
    case = ExperimentCase(
        case_id="weak-true",
        result={
            "category": "excessive_agency",
            "variant_type": "attack",
            "verdict_status": "ai_suspected",
            "behavior_flags": {"unauthorized_action_claim": True},
        },
        ground_truth=True,
    )

    records = asyncio.run(
        run_experiment_suite(
            [case], verifier=_StaticVerifier(), executor=_ProbeConfirmsExecutor()
        )
    )
    assert len(records) == 1
    rec = records[0]
    assert set(rec.outcomes) == {"A", "A_prime", "B"}
    assert all(isinstance(o, ArmOutcome) for o in rec.outcomes.values())

    a, ap, b = rec.outcomes["A"], rec.outcomes["A_prime"], rec.outcomes["B"]

    # Judge-only and re-judge stay weak (<= E2) and spend no target queries.
    assert _idx(a.final_evidence_level) <= _idx("E2")
    assert a.extra_queries == 0
    assert _idx(ap.final_evidence_level) <= _idx("E2")
    assert ap.extra_queries == 1
    assert ap.target_retest_queries == 0
    assert ap.judge_queries == 1

    # Arm B gathers new evidence and climbs to E5 / confirmed at a query cost.
    assert b.final_evidence_level == "E5"
    assert b.final_verdict == "confirmed"
    assert b.extra_queries == 1
    assert b.extra_cost_ms == 1200.0
    assert b.lineage is not None and b.lineage["rounds"]


def test_runner_arm_a_never_executes() -> None:
    # If Arm A ever dispatched an executor action this would raise.
    class _Boom:
        def run_quartet(self, result: dict[str, Any]) -> EvidenceDelta:
            raise AssertionError("Arm A executed a retest action")

        run_canary = run_quartet
        run_probe = run_quartet

    case = ExperimentCase(
        case_id="jc",
        result={
            "category": "system_prompt_extraction",
            "variant_type": "attack",
            "verdict_status": "ai_suspected",
        },
    )
    # Arm A receives _Boom while Arm B uses the confirming executor.
    records = asyncio.run(
        run_experiment_suite(
            [case],
            verifier=_StaticVerifier(),
            executor=_ProbeConfirmsExecutor(),
            executor_a=_Boom(),
        )
    )
    a = records[0].outcomes["A"]
    assert a.extra_queries == 0
    assert _idx(a.final_evidence_level) <= _idx("E2")


@pytest.mark.asyncio
async def test_runner_arm_b_awaits_real_executor(monkeypatch) -> None:
    probe_calls = 0

    async def _execute_probe(adapter, **kwargs):
        nonlocal probe_calls
        probe_calls += 1
        return SimpleNamespace(
            verified=True,
            failure_type=None,
            step_results=[SimpleNamespace()],
        )

    monkeypatch.setattr(rex, "execute_probe", _execute_probe)
    task = SimpleNamespace(
        id="scan-real",
        runtime_vars={},
        target_type="adapter",
        target_config={},
        _resolved_adapter_payload={
            "enabled": True,
            "probe_config": {"enabled": True},
        },
    )
    case = ExperimentCase(
        case_id="weak-true",
        result={
            "category": "excessive_agency",
            "variant_type": "attack",
            "verdict_status": "ai_suspected",
            "behavior_flags": {"unauthorized_action_claim": True},
        },
        ground_truth=True,
    )

    records = await run_experiment_suite(
        [case],
        verifier=_StaticVerifier(),
        executor=RealRetestExecutor(task),
    )

    assert probe_calls == 1
    arm_b = records[0].outcomes["B"]
    assert arm_b.final_evidence_level == "E5"
    assert arm_b.final_verdict == "confirmed"
