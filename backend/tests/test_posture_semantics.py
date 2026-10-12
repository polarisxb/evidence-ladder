from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AttackCase, AttackResult, ScanTask
from app.api import stats
from app.api.reports import _refresh_scan_rollups
from app.services.evidence_arbiter import arbitrate_evidence
from app.services.report_generator import generate_report, render_html_report
from app.services.risk_scorer import classify_overall_risk, compute_posture_metrics, scoring_result_payload
from app.services.scan_recovery import finalize_stuck_scan_from_db
from app.services.scan_comparison import compare_finding_names


def sample(verdict="manual_review_needed", **extra):
    return {
        "attack_successful": False, "risk_score": 0.0,
        "verdict_status": verdict, "target_response": "neutral fixture reply",
        "blackbox_outcome": "NO_INJECTION_SUCCESS",
        "response_evaluation": {"evaluation_validity": "evaluable"}, **extra,
    }


def saved_result(index=0, verdict="manual_review_needed", **extra):
    raw = sample(verdict, **extra)
    return AttackResult(
        id=f"semantic-{index}", scan_task_id="semantic-scan", template_id="fixture",
        category="prompt_injection", technique="fixture", attack_name="fixture",
        payload_text="fixture", target_response=raw["target_response"],
        attack_successful=raw["attack_successful"], confidence=0.0,
        risk_score=raw["risk_score"], risk_level="none", evidence="Judge request timed out",
        analysis_raw=raw, created_at=datetime.now(timezone.utc),
    )


def scan_with(results):
    return SimpleNamespace(
        id="semantic-scan", name="semantic fixture", target_url="https://fixture.example.com",
        status="completed", results=results, total_attacks=len(results), completed_attacks=len(results),
    )


@pytest.mark.parametrize("rows", [[], [sample()], [sample("not_evaluable")]])
def test_unavailable_evidence_has_no_posture_score(rows):
    metrics = compute_posture_metrics(rows)
    assert metrics["security_posture_score"] is None
    assert metrics["evaluable_tests"] == 0
    assert metrics["evaluation_coverage"] == 0
    assert classify_overall_risk(metrics["security_posture_score"]) == "unknown"


def test_mixed_evidence_exposes_coverage_and_never_counts_unknown_as_pass():
    metrics = compute_posture_metrics([sample(), sample("passed")])
    assert metrics["not_evaluable_tests"] == 1
    assert metrics["evaluable_tests"] == 1
    assert metrics["evaluation_coverage"] == 50
    assert metrics["security_posture_score"] == 50


@pytest.mark.parametrize("extra", [
    {"rule_hits": [{"rule": "fixture_rule"}]},
    {"business_verification_status": "probe_verified"},
    {"tool_observed": True, "tool_calls": [{"name": "fixture_tool"}]},
])
def test_judge_abstention_does_not_erase_stronger_evidence(extra):
    row = sample(**extra)
    assert arbitrate_evidence(row).is_evaluable
    assert compute_posture_metrics([row])["evaluable_tests"] == 1


def test_unattributed_tool_call_does_not_make_abstention_evaluable():
    row = sample(tool_calls=[{"name": "fixture_tool"}], sensitive_tools_fired=["fixture_tool"])
    assert compute_posture_metrics([row])["evaluable_tests"] == 0


def test_raw_legacy_rate_is_preserved_separately_from_evaluable_rate():
    metrics = compute_posture_metrics([sample(attack_successful=True)])
    assert metrics["attack_success_rate"] == 100.0
    assert metrics["evaluable_attack_success_rate"] is None
    assert metrics["security_posture_score"] is None


def test_timeout_report_agrees_with_arbiter_and_html_is_renderable():
    rows = [saved_result(i) for i in range(9)]
    for row in rows:
        row.analysis_raw["attack_goal_score"] = 0.0
    assert all(not arbitrate_evidence(row.analysis_raw).is_evaluable for row in rows)
    report = generate_report(scan_with(rows))
    assert report.overall_score is None
    assert report.risk_level == "unknown"
    assert report.evaluable_tests == 0
    assert report.not_evaluable_tests == 9
    assert report.evaluation_coverage == 0
    category = report.category_scores[0]
    assert category.pass_rate is None
    assert category.failed_attacks == 0
    assert category.not_evaluable_tests == 9
    assert report.evaluable_attack_success_rate is None
    assert report.average_attack_goal_score is None
    assert report.blackbox_outcome_breakdown["no_injection_success"] == 0
    assert report.blackbox_outcome_breakdown["unclassified"] == 9
    html = render_html_report(report)
    assert "Unable to score" in html
    assert "None" not in html
    assert "No critical issues found" not in html


def test_mixed_category_only_counts_evaluable_attack_failures():
    report = generate_report(scan_with([saved_result(0), saved_result(1, "passed")]))
    category = report.category_scores[0]
    assert category.total_tests == 2
    assert category.evaluable_tests == 1
    assert category.not_evaluable_tests == 1
    assert category.failed_attacks == 1
    assert category.evaluation_coverage == 50
    assert report.evaluation_status == "partial"


def test_completed_counter_does_not_hide_a_missing_result():
    task = scan_with([saved_result(0, "passed")])
    task.total_attacks = task.completed_attacks = 2
    report = generate_report(task)
    assert report.overall_score == 50
    assert report.evaluation_coverage == 50
    assert report.missing_results == 1
    assert report.evaluation_status == "partial"


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def seed(db, *, task_id="semantic-scan", status="completed", score=100.0, verdict="manual_review_needed"):
    task = ScanTask(
        id=task_id, name="semantic fixture", target_url="https://fixture.example.com",
        status=status, overall_score=score, total_attacks=1, completed_attacks=1,
    )
    row = saved_result(task_id, verdict)
    row.scan_task_id = task_id
    db.add_all([task, row])
    await db.commit()
    return task


@pytest.mark.anyio
async def test_review_rollup_and_recovery_do_not_keep_stale_perfect_score(db):
    task = await seed(db)
    await _refresh_scan_rollups(db, task.id)
    assert task.overall_score is None
    task.status = "cancelled"
    await db.commit()
    recovered = await finalize_stuck_scan_from_db(task.id, db)
    assert recovered["overall_score"] is None


@pytest.mark.anyio
async def test_unknown_score_cannot_generate_comparison_delta(db):
    a = await seed(db, task_id="unknown", score=None)
    b = await seed(db, task_id="known", score=100, verdict="passed")
    result = (await stats.compare_scans(a.id, b.id, db))["data"]
    assert result["score_diff"] is None
    assert result["scan_a"]["categories"]["prompt_injection"]["rate"] is None


@pytest.mark.anyio
async def test_zero_is_a_real_average_score(db):
    await seed(db, score=0)
    result = (await stats.get_overview_stats(db))["data"]
    assert result["avg_score"] == 0.0


@pytest.mark.anyio
async def test_unassessed_samples_are_not_compliance_passes(db):
    task = await seed(db, score=None)
    result = (await stats.get_compliance_score(task.id, db))["data"]
    tested = [row for row in result["owasp_results"] if row["total_tests"]]
    assert tested
    assert all(row["passed"] == 0 and row["score"] is None for row in tested)
    rates = (await stats.get_category_success_rate(db))["data"]
    assert rates[0]["rate"] is None


@pytest.mark.anyio
@pytest.mark.parametrize("side", ["fixed", "new"])
async def test_comparison_does_not_infer_change_from_unknown_counterpart(db, side):
    positive = await seed(db, task_id="positive", verdict="rule_verified", score=60)
    from sqlalchemy import select
    row = (await db.execute(select(AttackResult).where(AttackResult.scan_task_id == positive.id))).scalar_one()
    row.attack_successful = True
    unknown = await seed(db, task_id="unknown", score=None)
    a, b = (positive, unknown) if side == "fixed" else (unknown, positive)
    result = (await stats.compare_scans(a.id, b.id, db))["data"]
    assert result[f"{side}_vulnerabilities"] == []
    assert result["uncompared_vulnerabilities"] == ["fixture"]


def test_only_matching_evaluated_cases_can_establish_a_fix():
    positive = saved_result(0, "rule_verified", attack_successful=True)
    negative = saved_result(1, "passed")
    assert compare_finding_names([positive], [negative])["fixed_vulnerabilities"] == ["fixture"]
    negative.payload_text = "a different test prompt"
    comparison = compare_finding_names([positive], [negative])
    assert comparison["fixed_vulnerabilities"] == []
    assert comparison["uncompared_vulnerabilities"] == ["fixture"]


def test_nullable_case_tool_evidence_keeps_valid_raw_evidence():
    row = saved_result(tool_calls=[{"name": "fixture_tool"}])
    row.attack_case = AttackCase(summary_json={"tool_calls": None})
    assert scoring_result_payload(row)["tool_calls"] == [{"name": "fixture_tool"}]


def test_loaded_empty_case_summary_is_authoritative_over_stale_raw_summary():
    row = saved_result(case_summary={"tool_observed": True})
    row.attack_case = AttackCase(summary_json={})
    assert scoring_result_payload(row)["tool_observed"] is False
