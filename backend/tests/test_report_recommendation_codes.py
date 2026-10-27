"""Report recommendations carry stable codes the UI can translate."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import AttackResult
from app.services.report_generator import RECOMMENDATION_TEXT, generate_report


def _result(index: int, *, verdict: str, successful: bool, risk_score: float) -> AttackResult:
    raw = {
        "attack_successful": successful, "risk_score": risk_score, "verdict_status": verdict,
        "target_response": "fixture reply", "blackbox_outcome": "NO_INJECTION_SUCCESS",
        "response_evaluation": {"evaluation_validity": "evaluable"},
    }
    return AttackResult(
        id=f"codes-{index}", scan_task_id="codes-scan", template_id=f"fixture-{index}",
        category="jailbreak", technique="fixture", attack_name="fixture", payload_text="fixture",
        target_response="fixture reply", attack_successful=successful, confidence=0.9,
        risk_score=risk_score, risk_level="critical" if successful else "none",
        analysis_raw=raw, created_at=datetime.now(timezone.utc),
    )


def _scan(results):
    return SimpleNamespace(
        id="codes-scan", name="codes fixture", target_url="https://fixture.example.com",
        status="completed", results=results, total_attacks=len(results), completed_attacks=len(results),
    )


def test_codes_match_texts_in_order() -> None:
    report = generate_report(_scan([_result(i, verdict="passed", successful=False, risk_score=0) for i in range(3)]))

    assert report.recommendation_codes == ["no_critical_issues"]
    assert report.recommendations == [RECOMMENDATION_TEXT[c] for c in report.recommendation_codes]


def test_incomplete_evaluation_leads_and_drops_the_all_clear() -> None:
    report = generate_report(_scan([]))

    assert report.recommendation_codes[0] == "evaluation_incomplete"
    assert "no_critical_issues" not in report.recommendation_codes
    assert report.recommendations[0].startswith("Evaluation is incomplete.")


def test_failing_category_gets_its_own_code() -> None:
    results = [_result(i, verdict="rule_verified", successful=True, risk_score=9.5) for i in range(3)]

    report = generate_report(_scan(results))

    assert "jailbreak" in report.recommendation_codes
    assert report.recommendations == [RECOMMENDATION_TEXT[c] for c in report.recommendation_codes]
