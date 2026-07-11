# backend/app/tests/test_retest_loop/test_case_retest_lineage_model.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from app.database import Base
from app.models import CaseRetestLineage


@pytest.mark.asyncio
async def test_case_retest_lineage_roundtrip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as db:
        row = CaseRetestLineage(
            scan_task_id="scan-1",
            case_id="case-1",
            arm="B",
            retest_reason="text_claim_requires_probe",
            initial_evidence_level="E1",
            final_evidence_level="E5",
            final_verdict="confirmed",
            converged_reason="strong_evidence",
            total_extra_queries=3,
            total_extra_cost_ms=42.5,
            lineage_json={"case_id": "case-1", "rounds": []},
        )
        db.add(row)
        await db.commit()

    async with factory() as db:
        got = (await db.execute(select(CaseRetestLineage))).scalar_one()
        assert got.scan_task_id == "scan-1"
        assert got.arm == "B"
        assert got.final_verdict == "confirmed"
        assert got.total_extra_queries == 3
        assert got.total_extra_cost_ms == 42.5
        assert got.lineage_json == {"case_id": "case-1", "rounds": []}
        assert got.id and got.created_at is not None

    await engine.dispose()
