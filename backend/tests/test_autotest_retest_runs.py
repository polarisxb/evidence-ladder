import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session, init_db
from app.main import app
from app.models import AttackResult, AutoTestRetestRun, ScanTask

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_source_scan() -> tuple[str, list[str]]:
    async with async_session() as db:
        source = ScanTask(
            name="Persisted weak evidence source",
            status="completed",
            target_url="builtin",
            target_type="builtin_vulnerable",
            attack_categories=["jailbreak"],
            total_attacks=1,
            completed_attacks=1,
            advanced_config={"quartet_mode": "adaptive"},
        )
        db.add(source)
        await db.flush()

        result = AttackResult(
            scan_task_id=source.id,
            template_id="tpl-weak",
            category="jailbreak",
            technique="direct",
            attack_name="Weak judge-only finding",
            payload_text="bypass",
            target_response="complied",
            attack_successful=True,
            confidence=0.91,
            risk_level="medium",
            risk_score=5.0,
            analysis_raw={
                "variant_type": "attack",
                "verdict_status": "ai_suspected",
                "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                "rule_hits": [],
            },
        )
        db.add(result)
        await db.flush()
        source_id = source.id
        result_ids = [result.id]
        await db.commit()
    return source_id, result_ids


async def _cleanup_scans(*scan_ids: str) -> None:
    async with async_session() as db:
        runs = await db.execute(
            select(AutoTestRetestRun).where(
                (AutoTestRetestRun.source_scan_id.in_(scan_ids))
                | (AutoTestRetestRun.retest_scan_id.in_(scan_ids))
            )
        )
        for run in runs.scalars().all():
            await db.delete(run)
        for scan_id in scan_ids:
            task = await db.get(ScanTask, scan_id)
            if task is not None:
                await db.delete(task)
        await db.commit()


class TestAutoTestRetestRuns:
    async def test_create_scan_persists_retest_run_from_runtime_metadata(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def noop_run_scan(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)
        source_scan_id, source_result_ids = await _seed_source_scan()

        resp = await client.post("/api/v1/scans", json={
            "name": "Quartet retest scan",
            "target_type": "builtin_vulnerable",
            "target_url": "builtin",
            "target_config": {"vulnerable_level": 1},
            "attack_categories": ["jailbreak"],
            "runtime_vars": {
                "autotest_retest": {
                    "source_scan_id": source_scan_id,
                    "source_result_ids": source_result_ids,
                    "retest_reason": "judge_without_rule_evidence",
                    "retest_type": "quartet",
                },
            },
            "advanced": {"quartet_mode": "full"},
        })

        assert resp.status_code == 200
        retest_scan_id = resp.json()["data"]["task_id"]
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(AutoTestRetestRun).where(AutoTestRetestRun.retest_scan_id == retest_scan_id)
                )
                run = result.scalar_one_or_none()
                assert run is not None
                assert run.retest_scan_id == retest_scan_id
                assert run.source_scan_id == source_scan_id
                assert run.source_result_ids == source_result_ids
                assert run.retest_reason == "judge_without_rule_evidence"
                assert run.retest_type == "quartet"
                assert run.status == "created"
                assert run.outcome_counts == {}
                assert run.comparison_snapshot == []
        finally:
            await _cleanup_scans(retest_scan_id, source_scan_id)

    async def test_summary_uses_persisted_retest_run_and_updates_snapshot(
        self,
        client: AsyncClient,
    ) -> None:
        source_scan_id, source_result_ids = await _seed_source_scan()
        async with async_session() as db:
            retest = ScanTask(
                name="Persisted quartet retest",
                status="completed",
                target_url="builtin",
                target_type="builtin_vulnerable",
                attack_categories=["jailbreak"],
                total_attacks=1,
                completed_attacks=1,
                advanced_config={"quartet_mode": "full"},
            )
            db.add(retest)
            await db.flush()

            run = AutoTestRetestRun(
                retest_scan_id=retest.id,
                source_scan_id=source_scan_id,
                source_result_ids=source_result_ids,
                retest_reason="judge_without_rule_evidence",
                retest_type="quartet",
            )
            db.add(run)
            db.add(AttackResult(
                scan_task_id=retest.id,
                template_id="tpl-weak",
                category="jailbreak",
                technique="direct",
                attack_name="Weak judge-only finding",
                payload_text="bypass",
                target_response="complied with controls",
                attack_successful=True,
                confidence=0.95,
                risk_level="high",
                risk_score=8.0,
                analysis_raw={
                    "variant_type": "attack",
                    "verdict_status": "rule_verified",
                    "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                    "rule_hits": [{"rule": "quartet_delta", "evidence": "attack-only delta"}],
                    "quartet_validated": True,
                },
            ))
            await db.commit()
            retest_scan_id = retest.id

        try:
            resp = await client.get(f"/api/v1/autotest/scans/{retest_scan_id}/summary")

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["retest_source"]["source_scan_id"] == source_scan_id
            assert data["retest_run"]["retest_scan_id"] == retest_scan_id
            assert data["retest_run"]["source_result_ids"] == source_result_ids
            assert data["retest_outcome_counts"] == {
                "confirmed_by_retest": 1,
                "overturned_by_retest": 0,
                "manual_review_needed": 0,
            }

            async with async_session() as db:
                result = await db.execute(
                    select(AutoTestRetestRun).where(AutoTestRetestRun.retest_scan_id == retest_scan_id)
                )
                persisted = result.scalar_one_or_none()
                assert persisted is not None
                assert persisted.status == "summarized"
                assert persisted.outcome_counts == data["retest_outcome_counts"]
                assert persisted.comparison_snapshot == data["retest_comparisons"]
        finally:
            await _cleanup_scans(retest_scan_id, source_scan_id)
