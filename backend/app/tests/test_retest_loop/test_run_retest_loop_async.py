# backend/app/tests/test_retest_loop/test_run_retest_loop_async.py
import asyncio

from app.services.retest_policy import RetestConfig
from app.services.retest_loop import EvidenceDelta, run_retest_loop, run_retest_loop_async
from app.tests.test_retest_loop._fakes import AsyncFakeRetestExecutor, FakeRetestExecutor

ARM_B = RetestConfig(max_retest_rounds=2, quartet_enabled=True,
                     canary_enabled=True, probe_available=True)


def _run(coro):
    return asyncio.run(coro)


def test_async_initial_strong_evidence_confirms_without_retest():
    result = {"case_id": "c1", "business_verification_status": "probe_verified"}  # E5
    lineage = _run(run_retest_loop_async(result, AsyncFakeRetestExecutor(), ARM_B))
    assert lineage.final_verdict == "confirmed"
    assert lineage.rounds == []


def test_async_probe_upgrades_e1_text_claim_to_e5_confirmed():
    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1
    probe_delta = EvidenceDelta(action_type="run_probe",
                                evidence_updates={"business_verification_status": "probe_verified"},
                                extra_queries=1, extra_cost_ms=800.0, summary="state confirms send")
    lineage = _run(run_retest_loop_async(
        result, AsyncFakeRetestExecutor(probe=[probe_delta]), ARM_B))
    assert lineage.final_verdict == "confirmed"
    assert lineage.final_evidence_level == "E5"
    assert lineage.total_extra_queries == 1


def test_async_probe_failure_overturns_text_claim():
    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1
    probe_delta = EvidenceDelta(action_type="run_probe",
                                evidence_updates={"business_verification_status": "probe_failed"},
                                extra_queries=1, summary="no state change")
    lineage = _run(run_retest_loop_async(
        result, AsyncFakeRetestExecutor(probe=[probe_delta]), ARM_B))
    assert lineage.final_verdict == "overturned"
    assert lineage.converged_reason == "overturned"


def test_async_quoted_control_success_overturns_weak_judge_finding():
    result = {"case_id": "c1", "verdict_status": "ai_suspected"}  # E2
    quartet_delta = EvidenceDelta(action_type="run_quartet", contradiction=True,
                                  summary="quoted control also succeeded")
    lineage = _run(run_retest_loop_async(
        result, AsyncFakeRetestExecutor(quartet=[quartet_delta]), ARM_B))
    assert lineage.final_verdict == "overturned"


def test_async_matches_sync_lineage_for_same_script():
    result = {"case_id": "c1", "verdict_status": "ai_suspected"}  # E2 -> stall on no-op
    sync_lineage = run_retest_loop(result, FakeRetestExecutor(), ARM_B)
    async_lineage = _run(run_retest_loop_async(result, AsyncFakeRetestExecutor(), ARM_B))
    assert async_lineage.to_dict() == sync_lineage.to_dict()
