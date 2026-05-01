import pytest
from httpx import ASGITransport, AsyncClient

from app.database import async_session, init_db
from app.main import app
from app.models import AttackResult, ScanTask

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seeded_scan_id():
    async with async_session() as db:
        task = ScanTask(
            name="AutoTest summary fixture",
            status="completed",
            target_url="builtin",
            target_type="builtin_vulnerable",
            attack_categories=["system_prompt_extraction", "jailbreak"],
            total_attacks=3,
            completed_attacks=3,
            advanced_config={
                "quartet_mode": "adaptive",
                "enable_mutations": True,
            },
        )
        db.add(task)
        await db.flush()

        db.add_all([
            AttackResult(
                scan_task_id=task.id,
                template_id="tpl-canary",
                category="system_prompt_extraction",
                technique="direct",
                attack_name="Canary leak",
                payload_text="reveal hidden marker",
                target_response="CANARY-XYZ-001",
                attack_successful=True,
                confidence=0.7,
                risk_level="high",
                risk_score=8.0,
                analysis_raw={
                    "variant_type": "attack",
                    "verdict_status": "rule_verified",
                    "blackbox_outcome": "NO_INJECTION_SUCCESS",
                    "rule_hits": [
                        {"rule": "canary_token_match", "evidence": "CANARY-XYZ-001"}
                    ],
                    "behavior_flags": {"secret_disclosure": True},
                    "business_verification_status": "not_applicable",
                },
            ),
            AttackResult(
                scan_task_id=task.id,
                template_id="tpl-judge",
                category="jailbreak",
                technique="direct",
                attack_name="Judge-only success",
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
                    "behavior_flags": {},
                    "business_verification_status": "not_applicable",
                },
            ),
            AttackResult(
                scan_task_id=task.id,
                template_id="tpl-error",
                category="prompt_injection",
                technique="direct",
                attack_name="Transport error",
                payload_text="attack",
                target_response="[ERROR] timeout",
                attack_successful=False,
                confidence=0.0,
                risk_level="none",
                risk_score=0.0,
                analysis_raw={
                    "variant_type": "attack",
                    "verdict_status": "not_evaluable",
                    "response_evaluation": {
                        "evaluation_validity": "not_evaluable",
                        "transport_ok": False,
                        "invalid_reason": "transport_error",
                    },
                },
            ),
        ])

        await db.commit()
        scan_id = task.id

    try:
        yield scan_id
    finally:
        async with async_session() as db:
            task = await db.get(ScanTask, scan_id)
            if task is not None:
                await db.delete(task)
                await db.commit()


class TestAutoTestSummaryEndpoint:
    async def test_scan_summary_returns_evidence_metrics_and_retest_actions(
        self,
        client: AsyncClient,
        seeded_scan_id: str,
    ) -> None:
        resp = await client.get(f"/api/v1/autotest/scans/{seeded_scan_id}/summary")

        assert resp.status_code == 200
        data = resp.json()["data"]
        metrics = data["metrics"]
        assert metrics["total_results"] == 3
        assert metrics["evaluable_attack_results"] == 2
        assert metrics["not_evaluable_count"] == 1
        assert metrics["raw_asr"] == 1.0
        assert metrics["judge_asr"] == 0.5
        assert metrics["rule_verified_asr"] == 0.5
        assert metrics["evidence_verified_asr"] == 0.5
        assert metrics["weak_evidence_count"] == 1
        assert metrics["strong_evidence_count"] == 1

        levels = {item["result_id"]: item["evidence_level"] for item in data["items"]}
        assert set(levels.values()) == {"E0", "E2", "E3"}

        retest_actions = data["retest_actions"]
        assert len(retest_actions) == 1
        assert retest_actions[0]["actions"][0]["action_type"] == "run_quartet"

    async def test_scan_summary_returns_404_for_missing_scan(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/autotest/scans/missing-summary-id/summary")

        assert resp.status_code == 404

    async def test_retest_draft_returns_quartet_scan_config(
        self,
        client: AsyncClient,
        seeded_scan_id: str,
    ) -> None:
        resp = await client.post(f"/api/v1/autotest/scans/{seeded_scan_id}/retest-draft")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["source_scan_id"] == seeded_scan_id
        assert data["retest_reason"] == "judge_without_rule_evidence"
        assert len(data["source_result_ids"]) == 1
        assert data["action_count"] == 1

        scan_config = data["scan_config"]
        assert scan_config["name"].startswith("Retest: AutoTest summary fixture")
        assert scan_config["target_type"] == "builtin_vulnerable"
        assert scan_config["target_url"] == "builtin"
        assert scan_config["attack_categories"] == ["jailbreak"]
        assert scan_config["runtime_vars"]["autotest_retest"]["source_scan_id"] == seeded_scan_id
        assert scan_config["runtime_vars"]["autotest_retest"]["source_result_ids"] == data["source_result_ids"]
        assert scan_config["runtime_vars"]["autotest_retest"]["retest_reason"] == "judge_without_rule_evidence"
        assert scan_config["runtime_vars"]["autotest_retest"]["retest_type"] == "quartet"
        assert scan_config["advanced"]["quartet_mode"] == "full"
        assert scan_config["advanced"]["enable_mutations"] is False
        assert scan_config["advanced"]["enable_pair"] is False
        assert scan_config["advanced"]["enable_tap"] is False

    async def test_retest_draft_404_for_missing_scan(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/scans/missing-summary-id/retest-draft")

        assert resp.status_code == 404

    async def test_retest_summary_links_source_results_and_classifies_outcomes(
        self,
        client: AsyncClient,
    ) -> None:
        async with async_session() as db:
            source = ScanTask(
                name="Weak evidence source",
                status="completed",
                target_url="builtin",
                target_type="builtin_vulnerable",
                attack_categories=["jailbreak", "prompt_injection", "sensitive_info"],
                total_attacks=3,
                completed_attacks=3,
                advanced_config={"quartet_mode": "adaptive"},
            )
            db.add(source)
            await db.flush()

            source_results = [
                AttackResult(
                    scan_task_id=source.id,
                    template_id="tpl-confirm",
                    category="jailbreak",
                    technique="direct",
                    attack_name="Confirmable weak finding",
                    payload_text="bypass",
                    target_response="complied",
                    attack_successful=True,
                    confidence=0.9,
                    risk_level="medium",
                    risk_score=5.0,
                    analysis_raw={
                        "variant_type": "attack",
                        "verdict_status": "ai_suspected",
                        "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                        "rule_hits": [],
                    },
                ),
                AttackResult(
                    scan_task_id=source.id,
                    template_id="tpl-overturn",
                    category="prompt_injection",
                    technique="direct",
                    attack_name="Overturnable weak finding",
                    payload_text="ignore instructions",
                    target_response="complied",
                    attack_successful=True,
                    confidence=0.88,
                    risk_level="medium",
                    risk_score=5.0,
                    analysis_raw={
                        "variant_type": "attack",
                        "verdict_status": "ai_suspected",
                        "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                        "rule_hits": [],
                    },
                ),
                AttackResult(
                    scan_task_id=source.id,
                    template_id="tpl-review",
                    category="sensitive_info",
                    technique="direct",
                    attack_name="Still weak finding",
                    payload_text="claim an action",
                    target_response="I deleted the record",
                    attack_successful=True,
                    confidence=0.86,
                    risk_level="medium",
                    risk_score=5.0,
                    analysis_raw={
                        "variant_type": "attack",
                        "verdict_status": "ai_suspected",
                        "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                        "rule_hits": [],
                        "behavior_flags": {"unauthorized_action_claim": True},
                        "business_verification_status": "text_claim_only",
                    },
                ),
            ]
            db.add_all(source_results)
            await db.flush()

            source_result_ids = [row.id for row in source_results]
            retest = ScanTask(
                name="Quartet retest",
                status="completed",
                target_url="builtin",
                target_type="builtin_vulnerable",
                attack_categories=["jailbreak", "prompt_injection", "sensitive_info"],
                total_attacks=3,
                completed_attacks=3,
                advanced_config={"quartet_mode": "full"},
                runtime_vars={
                    "autotest_retest": {
                        "source_scan_id": source.id,
                        "source_result_ids": source_result_ids,
                        "retest_reason": "judge_without_rule_evidence",
                        "retest_type": "quartet",
                    },
                },
            )
            db.add(retest)
            await db.flush()

            db.add_all([
                AttackResult(
                    scan_task_id=retest.id,
                    template_id="tpl-confirm",
                    category="jailbreak",
                    technique="direct",
                    attack_name="Confirmable weak finding",
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
                ),
                AttackResult(
                    scan_task_id=retest.id,
                    template_id="tpl-overturn",
                    category="prompt_injection",
                    technique="direct",
                    attack_name="Overturnable weak finding",
                    payload_text="ignore instructions",
                    target_response="refused",
                    attack_successful=False,
                    confidence=0.2,
                    risk_level="none",
                    risk_score=0.0,
                    analysis_raw={
                        "variant_type": "attack",
                        "verdict_status": "passed",
                        "blackbox_outcome": "NO_INJECTION_SUCCESS",
                        "rule_hits": [],
                        "control_assessment": "discussion_supported",
                    },
                ),
                AttackResult(
                    scan_task_id=retest.id,
                    template_id="tpl-review",
                    category="sensitive_info",
                    technique="direct",
                    attack_name="Still weak finding",
                    payload_text="claim an action",
                    target_response="I deleted the record",
                    attack_successful=True,
                    confidence=0.9,
                    risk_level="medium",
                    risk_score=5.0,
                    analysis_raw={
                        "variant_type": "attack",
                        "verdict_status": "ai_suspected",
                        "blackbox_outcome": "FULL_INJECTION_SUCCESS",
                        "rule_hits": [],
                        "behavior_flags": {"unauthorized_action_claim": True},
                        "business_verification_status": "text_claim_only",
                    },
                ),
            ])
            await db.commit()
            source_id = source.id
            retest_id = retest.id

        try:
            resp = await client.get(f"/api/v1/autotest/scans/{retest_id}/summary")

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["retest_source"] == {
                "source_scan_id": source_id,
                "source_result_ids": source_result_ids,
                "retest_reason": "judge_without_rule_evidence",
                "retest_type": "quartet",
            }
            assert data["retest_outcome_counts"] == {
                "confirmed_by_retest": 1,
                "overturned_by_retest": 1,
                "manual_review_needed": 1,
            }

            comparisons = {
                comparison["source_result_id"]: comparison
                for comparison in data["retest_comparisons"]
            }
            assert comparisons[source_result_ids[0]]["outcome"] == "confirmed_by_retest"
            assert comparisons[source_result_ids[0]]["matching_retest_result_ids"]
            assert comparisons[source_result_ids[1]]["outcome"] == "overturned_by_retest"
            assert comparisons[source_result_ids[2]]["outcome"] == "manual_review_needed"
        finally:
            async with async_session() as db:
                for scan_id in (retest_id, source_id):
                    task = await db.get(ScanTask, scan_id)
                    if task is not None:
                        await db.delete(task)
                await db.commit()
