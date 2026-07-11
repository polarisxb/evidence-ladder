# backend/app/tests/test_retest_loop/test_run_retest_loop.py
from app.services.retest_policy import RetestConfig
from app.services.retest_loop import EvidenceDelta, run_retest_loop
from app.tests.test_retest_loop._fakes import FakeRetestExecutor

ARM_B = RetestConfig(max_retest_rounds=2, quartet_enabled=True,
                     canary_enabled=True, probe_available=True)


def test_initial_strong_evidence_confirms_without_retest():
    result = {"case_id": "c1", "business_verification_status": "probe_verified"}  # E5
    lineage = run_retest_loop(result, FakeRetestExecutor(), ARM_B)
    assert lineage.final_verdict == "confirmed"
    assert lineage.rounds == []  # no retest needed


def test_arm_a_judge_only_stops_at_e2():
    result = {"case_id": "c1", "verdict_status": "ai_suspected"}  # E2 + judge_without_rule_evidence
    lineage = run_retest_loop(result, FakeRetestExecutor(), RetestConfig(max_retest_rounds=0))
    assert lineage.final_verdict == "manual_review"
    assert lineage.converged_reason == "max_rounds"
    assert lineage.rounds == []


def test_probe_upgrades_e1_text_claim_to_e5_confirmed():
    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1, needs probe
    probe_delta = EvidenceDelta(action_type="run_probe",
                                evidence_updates={"business_verification_status": "probe_verified"},
                                extra_queries=1, extra_cost_ms=800.0, summary="state confirms send")
    lineage = run_retest_loop(result, FakeRetestExecutor(probe=[probe_delta]), ARM_B)
    assert lineage.final_verdict == "confirmed"
    assert lineage.final_evidence_level == "E5"
    assert lineage.total_extra_queries == 1


def test_probe_failure_overturns_text_claim():
    result = {"case_id": "c1", "behavior_flags": {"unauthorized_action_claim": True}}  # E1
    probe_delta = EvidenceDelta(action_type="run_probe",
                                evidence_updates={"business_verification_status": "probe_failed"},
                                extra_queries=1, summary="no state change")
    lineage = run_retest_loop(result, FakeRetestExecutor(probe=[probe_delta]), ARM_B)
    assert lineage.final_verdict == "overturned"
    assert lineage.converged_reason == "overturned"


def test_quoted_control_success_overturns_weak_judge_finding():
    result = {"case_id": "c1", "verdict_status": "ai_suspected"}  # E2, judge_without_rule_evidence
    quartet_delta = EvidenceDelta(action_type="run_quartet", contradiction=True,
                                  summary="quoted control also succeeded")
    lineage = run_retest_loop(result, FakeRetestExecutor(quartet=[quartet_delta]), ARM_B)
    assert lineage.final_verdict == "overturned"


def test_stall_when_retest_gathers_nothing():
    result = {"case_id": "c1", "verdict_status": "ai_suspected"}  # E2
    # FakeRetestExecutor default returns no-op deltas -> level stays E2 -> stall
    lineage = run_retest_loop(result, FakeRetestExecutor(), ARM_B)
    assert lineage.final_verdict == "manual_review"
    assert lineage.converged_reason in {"stall", "max_rounds"}
    assert len(lineage.rounds) >= 1
