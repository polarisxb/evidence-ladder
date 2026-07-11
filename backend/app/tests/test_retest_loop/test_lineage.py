# backend/app/tests/test_retest_loop/test_lineage.py
from app.services.retest_loop import RetestLineage, RetestRound


def test_lineage_totals_and_serialization():
    lineage = RetestLineage(
        case_id="c1", initial_evidence_level="E2", initial_conflict_types=("judge_without_rule_evidence",),
        rounds=[
            RetestRound(round_index=1, trigger_conflicts=("judge_without_rule_evidence",),
                        actions=({"type": "run_quartet", "reason": "judge_without_rule_evidence"},),
                        evidence_before="E2", evidence_after="E3", delta_summary="only-attack triggered",
                        extra_queries=3, extra_cost_ms=1200.0),
        ],
        final_verdict="confirmed", final_evidence_level="E3", converged_reason="strong_evidence",
    )
    assert lineage.total_extra_queries == 3
    assert lineage.total_extra_cost_ms == 1200.0
    d = lineage.to_dict()
    assert d["final_verdict"] == "confirmed"
    assert d["rounds"][0]["evidence_after"] == "E3"
