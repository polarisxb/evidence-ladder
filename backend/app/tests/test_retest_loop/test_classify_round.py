# backend/app/tests/test_retest_loop/test_classify_round.py
from app.services.evidence_arbiter import arbitrate_evidence
from app.services.retest_policy import RetestConfig
from app.services.retest_loop import classify_round


def _assess(result):
    return arbitrate_evidence(result)


def test_strong_evidence_confirms():
    a = _assess({"business_verification_status": "probe_verified"})  # E5
    d = classify_round(assessment=a, contradicted=False, level_before="E1",
                       rounds_used=1, config=RetestConfig(max_retest_rounds=2))
    assert (d.terminal, d.verdict, d.reason) == (True, "confirmed", "strong_evidence")


def test_strong_evidence_beats_contradiction():
    a = _assess({"business_verification_status": "probe_verified"})  # E5
    d = classify_round(assessment=a, contradicted=True, level_before="E1",
                       rounds_used=1, config=RetestConfig(max_retest_rounds=2))
    assert d.verdict == "confirmed"  # D3: strong wins over quoted-contradiction


def test_contradiction_overturns_when_weak():
    a = _assess({"verdict_status": "ai_suspected"})  # E2, weak
    d = classify_round(assessment=a, contradicted=True, level_before="E2",
                       rounds_used=1, config=RetestConfig(max_retest_rounds=2))
    assert (d.verdict, d.reason) == ("overturned", "overturned")


def test_max_rounds_exhausted_is_manual_review():
    a = _assess({"verdict_status": "ai_suspected"})  # E2
    d = classify_round(assessment=a, contradicted=False, level_before="E2",
                       rounds_used=2, config=RetestConfig(max_retest_rounds=2))
    assert (d.verdict, d.reason) == ("manual_review", "max_rounds")


def test_stall_when_level_unchanged_is_manual_review():
    a = _assess({"verdict_status": "ai_suspected"})  # E2
    d = classify_round(assessment=a, contradicted=False, level_before="E2",
                       rounds_used=1, config=RetestConfig(max_retest_rounds=2))
    assert (d.verdict, d.reason) == ("manual_review", "stall")


def test_upgraded_but_still_weak_continues():
    a = _assess({"verdict_status": "ai_suspected"})  # E2
    d = classify_round(assessment=a, contradicted=False, level_before=None,
                       rounds_used=1, config=RetestConfig(max_retest_rounds=2))
    assert d.terminal is False


def test_not_evaluable():
    a = _assess({"verdict_status": "not_evaluable"})  # E0
    d = classify_round(assessment=a, contradicted=False, level_before=None,
                       rounds_used=0, config=RetestConfig(max_retest_rounds=2))
    assert (d.verdict, d.reason) == ("not_evaluable", "not_evaluable")
