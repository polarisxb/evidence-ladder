# backend/app/tests/test_retest_loop/test_retest_writeback.py
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AttackCase, AttackResult
from app.services import retest_orchestrator as orch
from app.services.retest_loop import RetestLineage, RetestRound


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _lineage():
    lineage = RetestLineage(
        case_id="case-1",
        initial_evidence_level="E1",
        initial_conflict_types=("secret_disclosure_suspected",),
    )
    lineage.rounds.append(
        RetestRound(
            round_index=1,
            trigger_conflicts=("secret_disclosure_suspected",),
            actions=({"action_type": "run_canary_retest", "reason": "x"},),
            evidence_before="E1",
            evidence_after="E3",
            delta_summary="canary observed",
            extra_queries=1,
            extra_cost_ms=1500.0,
        )
    )
    lineage.final_verdict = "confirmed"
    lineage.final_evidence_level = "E3"
    lineage.converged_reason = "strong_evidence"
    return lineage


async def _seed_case(db, *, scan_id="scan-1", case_id="case-1"):
    result = AttackResult(
        id="res-1",
        scan_task_id=scan_id,
        template_id="SP-001",
        category="system_prompt_extraction",
        technique="t",
        attack_name="n",
        payload_text="p",
        target_response="r",
        attack_successful=True,
        risk_level="high",
        risk_score=7.0,
        analysis_raw={"verdict_status": "ai_suspected"},
    )
    db.add(result)
    await db.flush()
    case = AttackCase(
        id=case_id,
        scan_task_id=scan_id,
        template_id="SP-001",
        category="system_prompt_extraction",
        technique="t",
        attack_name="n",
        legacy_attack_result_id=result.id,
        summary_json={"verdict_status": "ai_suspected"},
    )
    db.add(case)
    await db.commit()
    return result, case


@pytest.mark.asyncio
async def test_apply_retest_writeback_annotates_result_and_case():
    engine, factory = await _factory()
    async with factory() as db:
        await _seed_case(db)

    async with factory() as db:
        await orch.apply_retest_writeback(
            db,
            task=types.SimpleNamespace(id="scan-1"),
            case_id="case-1",
            arm="B",
            lineage=_lineage(),
        )

    async with factory() as db:
        res = (await db.execute(select(AttackResult))).scalar_one()
        case = (await db.execute(select(AttackCase))).scalar_one()
        # non-destructive: original headline fields untouched
        assert res.attack_successful is True
        assert res.risk_level == "high"
        # retest conclusion attached to both read paths
        for blob in (res.analysis_raw["retest"], case.summary_json["retest"]):
            assert blob["arm"] == "B"
            assert blob["initial_evidence_level"] == "E1"
            assert blob["final_evidence_level"] == "E3"
            assert blob["final_verdict"] == "confirmed"
            assert blob["converged_reason"] == "strong_evidence"
            assert blob["total_extra_queries"] == 1
            assert blob["total_extra_cost_ms"] == 1500.0
        # existing analysis_raw keys preserved
        assert res.analysis_raw["verdict_status"] == "ai_suspected"
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_retest_writeback_missing_case_is_noop():
    engine, factory = await _factory()
    async with factory() as db:
        # no case seeded
        await orch.apply_retest_writeback(
            db,
            task=types.SimpleNamespace(id="scan-1"),
            case_id="nope",
            arm="B",
            lineage=_lineage(),
        )
    async with factory() as db:
        assert (await db.execute(select(AttackResult))).all() == []
    await engine.dispose()
