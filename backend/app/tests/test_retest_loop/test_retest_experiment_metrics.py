# backend/app/tests/test_retest_loop/test_retest_experiment_metrics.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import CaseRetestLineage
from app.services import retest_orchestrator as orch


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _row(scan, arm, verdict, q, cost):
    return CaseRetestLineage(
        scan_task_id=scan, case_id=f"c-{arm}-{verdict}-{q}", arm=arm,
        final_verdict=verdict, total_extra_queries=q, total_extra_cost_ms=cost,
        lineage_json={},
    )


@pytest.mark.asyncio
async def test_aggregate_groups_by_arm():
    engine, factory = await _factory()
    async with factory() as db:
        db.add_all([
            _row("scan-1", "A", "manual_review", 0, 0.0),
            _row("scan-1", "A", "manual_review", 0, 0.0),
            _row("scan-1", "B", "confirmed", 2, 10.0),
            _row("scan-1", "B", "overturned", 1, 4.0),
            _row("scan-1", "B", "confirmed", 3, 16.0),
            _row("scan-2", "B", "confirmed", 9, 99.0),  # different scan, excluded
        ])
        await db.commit()

    async with factory() as db:
        metrics = await orch.aggregate_retest_experiment(db, "scan-1")

    assert set(metrics) == {"A", "B"}
    assert metrics["A"]["total"] == 2
    assert metrics["A"]["verdicts"]["manual_review"] == 2
    assert metrics["A"]["total_extra_queries"] == 0

    b = metrics["B"]
    assert b["total"] == 3
    assert b["verdicts"]["confirmed"] == 2
    assert b["verdicts"]["overturned"] == 1
    assert b["total_extra_queries"] == 6
    assert b["mean_extra_queries"] == pytest.approx(2.0)
    assert b["mean_extra_cost_ms"] == pytest.approx(10.0)
    await engine.dispose()


@pytest.mark.asyncio
async def test_aggregate_empty_scan_is_empty():
    engine, factory = await _factory()
    async with factory() as db:
        metrics = await orch.aggregate_retest_experiment(db, "nope")
    assert metrics == {}
    await engine.dispose()
