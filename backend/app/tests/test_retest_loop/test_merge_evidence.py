# backend/app/tests/test_retest_loop/test_merge_evidence.py
from app.services.retest_loop import EvidenceDelta, merge_evidence


def test_merge_sets_top_level_key_without_mutating_input():
    result = {"business_verification_status": "text_claim_only"}
    delta = EvidenceDelta(action_type="run_probe",
                          evidence_updates={"business_verification_status": "probe_verified"})
    merged = merge_evidence(result, delta)
    assert merged["business_verification_status"] == "probe_verified"
    assert result["business_verification_status"] == "text_claim_only"  # input untouched


def test_merge_deep_updates_nested_mapping():
    result = {"behavior_flags": {"unauthorized_action_claim": True}}
    delta = EvidenceDelta(action_type="run_canary",
                          evidence_updates={"behavior_flags": {"secret_disclosure": True}})
    merged = merge_evidence(result, delta)
    assert merged["behavior_flags"] == {"unauthorized_action_claim": True, "secret_disclosure": True}
