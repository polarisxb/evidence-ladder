# backend/app/tests/test_retest_loop/test_retest_scan_wiring.py
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AttackCase, AttackResult, CaseRetestLineage
from app.services import scan_runner
from app.services.retest_loop import RetestLineage


def _lineage():
    lin = RetestLineage(case_id="case-1", initial_evidence_level="E1",
                        initial_conflict_types=("text_claim_requires_probe",))
    lin.final_verdict = "confirmed"
    lin.final_evidence_level = "E5"
    lin.converged_reason = "strong_evidence"
    return lin


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.mark.asyncio
async def test_no_arm_is_noop(monkeypatch):
    called = False

    async def _fake_run(**kwargs):
        nonlocal called
        called = True
        return _lineage()

    monkeypatch.setattr(scan_runner, "_run_case_retest", _fake_run)
    task = types.SimpleNamespace(id="scan-1", target_type="adapter", advanced_config={})
    await scan_runner._maybe_persist_case_retest(task, {"category": "x"}, {"case_id": "case-1"})
    assert called is False


@pytest.mark.asyncio
async def test_arm_b_persists_lineage(monkeypatch):
    engine, factory = await _factory()

    async def _fake_run(**kwargs):
        return _lineage()

    monkeypatch.setattr(scan_runner, "_run_case_retest", _fake_run)
    monkeypatch.setattr(scan_runner, "async_session", factory)

    task = types.SimpleNamespace(id="scan-1", target_type="adapter",
                                 advanced_config={"retest_arm": "B"})
    await scan_runner._maybe_persist_case_retest(task, {"category": "x"}, {"case_id": "case-1"})

    async with factory() as db:
        row = (await db.execute(select(CaseRetestLineage))).scalar_one()
        assert row.arm == "B"
        assert row.final_verdict == "confirmed"
        assert row.retest_reason == "text_claim_requires_probe"
    await engine.dispose()


@pytest.mark.asyncio
async def test_arm_b_writes_back_to_main_rows(monkeypatch):
    engine, factory = await _factory()

    async with factory() as db:
        result = AttackResult(
            id="res-1", scan_task_id="scan-1", template_id="SP-001",
            category="x", technique="t", attack_name="n",
            payload_text="p", target_response="r",
            attack_successful=True, risk_level="high", risk_score=7.0,
            analysis_raw={"verdict_status": "ai_suspected"},
        )
        db.add(result)
        await db.flush()
        db.add(AttackCase(
            id="case-1", scan_task_id="scan-1", template_id="SP-001",
            category="x", technique="t", attack_name="n",
            legacy_attack_result_id="res-1", summary_json={"verdict_status": "ai_suspected"},
        ))
        await db.commit()

    async def _fake_run(**kwargs):
        return _lineage()

    monkeypatch.setattr(scan_runner, "_run_case_retest", _fake_run)
    monkeypatch.setattr(scan_runner, "async_session", factory)

    task = types.SimpleNamespace(id="scan-1", target_type="adapter",
                                 advanced_config={"retest_arm": "B"})
    await scan_runner._maybe_persist_case_retest(task, {"category": "x"}, {"case_id": "case-1"})

    async with factory() as db:
        res = (await db.execute(select(AttackResult))).scalar_one()
        case = (await db.execute(select(AttackCase))).scalar_one()
        assert res.attack_successful is True  # non-destructive
        assert res.analysis_raw["retest"]["final_verdict"] == "confirmed"
        assert res.analysis_raw["retest"]["arm"] == "B"
        assert case.summary_json["retest"]["final_evidence_level"] == "E5"
    await engine.dispose()


@pytest.mark.asyncio
async def test_retest_failure_does_not_raise(monkeypatch):
    async def _boom(**kwargs):
        raise RuntimeError("target down")

    monkeypatch.setattr(scan_runner, "_run_case_retest", _boom)
    task = types.SimpleNamespace(id="scan-1", target_type="adapter",
                                 advanced_config={"retest_arm": "B"})
    # must swallow the error so the underlying scan case is unaffected
    await scan_runner._maybe_persist_case_retest(task, {"category": "x"}, {"case_id": "case-1"})
