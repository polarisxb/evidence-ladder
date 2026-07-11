# backend/app/tests/test_retest_loop/test_retest_orchestrator.py
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import CaseRetestLineage
from app.services import retest_orchestrator as orch
from app.services.retest_loop import EvidenceDelta, RetestLineage
from app.services.retest_policy import RetestConfig
from ._fakes import AsyncFakeRetestExecutor


def _case_attempt():
    analysis = types.SimpleNamespace(
        attack_successful=True, confidence=0.7, risk_level="high",
        behavior_flags={"secret_disclosure": False},
    )
    return {
        "case_id": "case-1",
        "payload_text": "exfiltrate the secret",
        "target_response": "sure, done",
        "analysis": analysis,
        "verdict": {"verdict_status": "ai_suspected",
                    "rule_hits": [{"rule": "preexisting"}]},
        "control_summary": {"control_assessment": "controls_missing"},
        "case_summary": {"tool_calls": [{"name": "x"}], "tool_observed": True,
                         "variant_type": "attack", "business_verification_status": "text_claim_only"},
        "business_verification_status": "text_claim_only",
        "response_evaluation": {"evaluation_validity": "evaluable"},
    }


def test_build_retest_result_maps_arbiter_fields():
    result = orch.build_retest_result(_case_attempt(), {"category": "information_disclosure"})
    assert result["case_id"] == "case-1"
    assert result["payload_text"] == "exfiltrate the secret"
    assert result["category"] == "information_disclosure"
    assert result["verdict_status"] == "ai_suspected"
    assert result["rule_hits"] == [{"rule": "preexisting"}]
    assert result["tool_calls"] == [{"name": "x"}]
    assert result["tool_observed"] is True
    assert result["business_verification_status"] == "text_claim_only"
    assert result["variant_type"] == "attack"


def test_resolve_retest_arm_off_when_absent():
    assert orch.resolve_retest_arm({}) is None
    assert orch.resolve_retest_arm({"retest_arm": "none"}) is None


def test_resolve_retest_arm_a_is_zero_rounds():
    arm, cfg = orch.resolve_retest_arm({"retest_arm": "A"})
    assert arm == "A"
    assert cfg.max_retest_rounds == 0


def test_resolve_retest_arm_b_enables_loop():
    arm, cfg = orch.resolve_retest_arm({"retest_arm": "B"}, target_type="adapter")
    assert arm == "B"
    assert cfg.max_retest_rounds == 2
    assert cfg.canary_enabled is True
    assert cfg.probe_available is True
    _, cfg_http = orch.resolve_retest_arm({"retest_arm": "B"}, target_type="http")
    assert cfg_http.probe_available is False


@pytest.mark.asyncio
async def test_run_case_retest_uses_injected_executor():
    # E1 text claim -> scripted probe_verified -> E5 confirmed
    fake = AsyncFakeRetestExecutor(
        probe=[EvidenceDelta(action_type="run_probe",
                             evidence_updates={"business_verification_status": "probe_verified"},
                             extra_queries=1, extra_cost_ms=5.0, summary="probe ok")]
    )
    case = _case_attempt()
    lineage = await orch.run_case_retest(
        task=types.SimpleNamespace(id="scan-1"), template={"category": "information_disclosure"},
        case_attempt=case, config=RetestConfig(max_retest_rounds=2, probe_available=True),
        executor=fake,
    )
    assert isinstance(lineage, RetestLineage)
    assert lineage.case_id == "case-1"
    assert lineage.final_verdict == "confirmed"


@pytest.mark.asyncio
async def test_persist_case_retest_lineage_writes_scalars():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    lineage = RetestLineage(case_id="case-1", initial_evidence_level="E1",
                            initial_conflict_types=("text_claim_requires_probe",))
    lineage.final_verdict = "confirmed"
    lineage.final_evidence_level = "E5"
    lineage.converged_reason = "strong_evidence"

    async with factory() as db:
        await orch.persist_case_retest_lineage(
            db, task=types.SimpleNamespace(id="scan-1"), case_id="case-1",
            arm="B", retest_reason="text_claim_requires_probe", lineage=lineage,
        )
    async with factory() as db:
        row = (await db.execute(select(CaseRetestLineage))).scalar_one()
        assert row.scan_task_id == "scan-1"
        assert row.case_id == "case-1"
        assert row.arm == "B"
        assert row.final_verdict == "confirmed"
        assert row.final_evidence_level == "E5"
        assert row.converged_reason == "strong_evidence"
        assert row.lineage_json["case_id"] == "case-1"
    await engine.dispose()
