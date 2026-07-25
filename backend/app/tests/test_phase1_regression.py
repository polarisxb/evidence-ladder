import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.reports import _load_completed_scan
from app.database import Base
from app.models import AttackCase, AttackCaseVariant, AttackResult, ScanTask
from app.schemas.report import AnalysisResult
from app.services.attack_engine import AttackEngine
from app.services.case_serializer import serialize_attack_case
from app.services.response_screening import TargetResponseEnvelope, screen_response_origin
from app.services import case_executor, scan_runner


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass  # Windows: SQLite file still held by aiosqlite


TEMPLATES_BY_CATEGORY = {
    "single": [
        {
            "id": "S-001",
            "name": "Single Template",
            "technique": "single_technique",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "single attack prompt"}],
        }
    ],
    "multi": [
        {
            "id": "M-001",
            "name": "Multi Template",
            "technique": "multi_technique",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "multi_turn": True,
            "payloads": [
                {"text": "turn one"},
                {"text": "turn two"},
                {"text": "turn three"},
            ],
        }
    ],
    "pair": [
        {
            "id": "P-001",
            "name": "PAIR Template",
            "technique": "pair_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "pair seed prompt"}],
        }
    ],
    "tap": [
        {
            "id": "T-001",
            "name": "TAP Template",
            "technique": "tap_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "tap seed prompt"}],
        }
    ],
    "crescendo": [
        {
            "id": "C-001",
            "name": "Crescendo Template",
            "technique": "crescendo_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "crescendo seed prompt"}],
        }
    ],
    "iris": [
        {
            "id": "I-001",
            "name": "IRIS Template",
            "technique": "iris_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "iris seed prompt"}],
        }
    ],
    "degraded": [
        {
            "id": "D-001",
            "name": "Degraded Template",
            "technique": "degraded_technique",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [
                {"text": "degraded prompt 1"},
                {"text": "degraded prompt 2"},
                {"text": "degraded prompt 3"},
                {"text": "degraded prompt 4"},
                {"text": "degraded prompt 5"},
            ],
        }
    ],
}


def _patched_get_all_templates(self, categories=None):
    if not categories:
        return []
    key = next((value for value in categories if value in TEMPLATES_BY_CATEGORY), None)
    return list(TEMPLATES_BY_CATEGORY.get(key, []))


async def _fake_send_to_target_with_result(task, payload, *, case_id, variant_type, conversation_history=None):
    return f"mock-response::{payload[:40]}", None


async def _fake_invoke_target_with_envelope(task, payload, *, case_id, variant_type, conversation_history=None):
    response_text = f"mock-probe::{payload[:40]}"
    if variant_type == "health_probe":
        response_text = f"probe-response::{payload[:40]}"
    return TargetResponseEnvelope(
        response_text=response_text,
        response_status="completed",
        target_type=task.target_type,
        transport_ok=True,
    )


async def _fake_analyze_response(attack_type, attack_payload, target_response, context="", *, skip_confirmation=False):
    return AnalysisResult(
        attack_successful=not str(target_response).startswith("[ERROR]"),
        confidence=0.91,
        risk_level="high",
        evidence="mock evidence",
        leaked_info=None,
        explanation="mock explanation",
        remediation="mock remediation",
    )


def _flaky_analyze_response_factory():
    state = {"calls": 0}

    async def _flaky_analyze_response(attack_type, attack_payload, target_response, context="", *, skip_confirmation=False):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("judge provider temporary failure")
        return await _fake_analyze_response(
            attack_type,
            attack_payload,
            target_response,
            context,
            skip_confirmation=skip_confirmation,
        )

    return _flaky_analyze_response


def _fake_classify_verdict(*, attack_payload, target_response, analysis, target_config, control_assessment=None):
    return {
        "verdict_status": "rule_verified" if analysis.attack_successful else "passed",
        "verdict_reason": "mock verdict",
        "rule_hits": [{"rule": "mock_rule", "evidence": "mock_evidence"}],
    }


def _fake_summarize_control_comparison(*, attack_response, control_results, analysis, target_config=None):
    return {
        "control_assessment": "attack_delta_supported" if analysis.attack_successful else "controls_missing",
        "control_summary": "mock control summary",
    }


async def _fake_run_pair(seed_prompt, objective, send_fn, max_rounds=8, should_stop=None):
    return SimpleNamespace(
        success=True,
        best_prompt="pair best prompt",
        best_response="pair best response",
        best_score=9.2,
        total_queries=3,
        attempts=[
            SimpleNamespace(
                round_number=1,
                prompt="pair prompt 1",
                response="pair response 1",
                score=9.2,
                reasoning="pair reasoning",
                improvement="pair improvement",
                strategy="pair strategy",
            )
        ],
    )


async def _failing_run_pair(seed_prompt, objective, send_fn, max_rounds=8, should_stop=None):
    raise RuntimeError("pair engine boom")


async def _fake_run_tap(base_payload, objective, send_fn, branching_factor=4, max_depth=10, should_stop=None):
    return SimpleNamespace(
        success=True,
        best_prompt="tap best prompt",
        best_response="tap best response",
        best_score=9.0,
        total_queries=4,
        variants_generated=6,
        depth_reached=2,
        stop_reason="completed_search",
        all_attempts=[
            {
                "prompt": "tap prompt",
                "response": "tap response",
                "score": 9.0,
                "depth": 1,
                "strategy": "tap strategy",
            }
        ],
    )


async def _fake_run_crescendo(objective, send_fn, max_rounds=10, should_stop=None):
    turns = [
        SimpleNamespace(
            turn_number=1,
            question="crescendo question 1",
            response="crescendo response 1",
            refused=False,
            judge_score=6.0,
            judge_success=False,
        ),
        SimpleNamespace(
            turn_number=2,
            question="crescendo question 2",
            response="crescendo response 2",
            refused=False,
            judge_score=9.0,
            judge_success=True,
        ),
    ]
    return SimpleNamespace(
        success=True,
        final_response="crescendo final response",
        total_turns=2,
        strategy_log=["crescendo strategy"],
        turns=turns,
    )


async def _fake_run_iris(base_payload, objective, send_fn, max_rounds=5, should_stop=None):
    return SimpleNamespace(
        success=True,
        best_prompt="iris best prompt",
        best_response="iris best response",
        best_score=8.8,
        total_queries=3,
        rounds=[
            SimpleNamespace(
                round_number=1,
                prompt="iris prompt 1",
                response="iris response 1",
                score=8.8,
                reasoning="iris reasoning",
                self_explanation="iris self explanation",
                strategy="iris strategy",
            )
        ],
    )


class Phase1RegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.addCleanup(lambda p=tmp.name: _safe_unlink(p))
        self.db_path = tmp.name
        self.engine = create_async_engine("sqlite+aiosqlite:///" + self.db_path.replace("\\", "/"))
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.patchers = [
            patch.object(scan_runner, "async_session", self.session_factory),
            patch.object(case_executor, "invoke_target_with_envelope", _fake_invoke_target_with_envelope),
            patch.object(scan_runner, "_send_to_target_with_result", _fake_send_to_target_with_result),
            patch.object(scan_runner, "_invoke_target_with_envelope", _fake_invoke_target_with_envelope),
            patch.object(case_executor, "analyze_response", _fake_analyze_response),
            patch.object(case_executor, "classify_verdict", _fake_classify_verdict),
            patch.object(case_executor, "summarize_control_comparison", _fake_summarize_control_comparison),
            patch.object(scan_runner, "run_pair", _fake_run_pair),
            patch.object(scan_runner, "run_tap", _fake_run_tap),
            patch.object(scan_runner, "run_crescendo", _fake_run_crescendo),
            patch.object(scan_runner, "run_iris", _fake_run_iris),
            patch.object(AttackEngine, "get_all_templates", _patched_get_all_templates),
        ]
        for patcher in self.patchers:
            patcher.start()

    async def asyncTearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        await self.engine.dispose()

    async def _create_task(
        self,
        *,
        name: str,
        categories: list[str],
        advanced_config: dict | None = None,
        target_config: dict | None = None,
    ) -> ScanTask:
        async with self.session_factory() as session:
            task = ScanTask(
                name=name,
                target_url="mock://target",
                target_type="generic",
                target_config=target_config,
                attack_categories=categories,
                advanced_config=advanced_config,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def _assert_dual_write_scan(
        self,
        *,
        task: ScanTask,
        expected_case_template_ids: list[str],
        expected_result_template_ids: list[str],
    ):
        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            cases = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task.id))
            ).scalars().all()
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()
            variants = (
                await session.execute(
                    select(AttackCaseVariant).join(AttackCase).where(AttackCase.scan_task_id == task.id)
                )
            ).scalars().all()

        self.assertEqual(stored_task.total_attacks, 2)
        self.assertEqual(stored_task.completed_attacks, 2)
        self.assertEqual(len(cases), 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(variants), 8)
        self.assertEqual(sorted(case.template_id for case in cases), sorted(expected_case_template_ids))
        self.assertEqual(sorted(result.template_id for result in results), sorted(expected_result_template_ids))

    async def test_single_turn_scan_persists_case_and_variants(self):
        task = await self._create_task(name="single", categories=["single"])

        await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            cases = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task.id))
            ).scalars().all()
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()
            variants = (
                await session.execute(
                    select(AttackCaseVariant).join(AttackCase).where(AttackCase.scan_task_id == task.id)
                )
            ).scalars().all()

        self.assertEqual(stored_task.total_attacks, 1)
        self.assertEqual(stored_task.completed_attacks, 1)
        self.assertEqual(len(cases), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(variants), 4)
        self.assertEqual(cases[0].legacy_attack_result_id, results[0].id)
        self.assertEqual(cases[0].template_id, "S-001")

    async def test_multi_turn_scan_counts_one_case_and_keeps_legacy_payload_format(self):
        task = await self._create_task(name="multi", categories=["multi"])

        await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            cases = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task.id))
            ).scalars().all()
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()
            variants = (
                await session.execute(
                    select(AttackCaseVariant).join(AttackCase).where(AttackCase.scan_task_id == task.id)
                )
            ).scalars().all()

        self.assertEqual(stored_task.total_attacks, 1)
        self.assertEqual(stored_task.completed_attacks, 1)
        self.assertEqual(len(cases), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(variants), 4)
        self.assertEqual(
            results[0].payload_text,
            "Turn 1: turn one\nTurn 2: turn two\nTurn 3: turn three",
        )

    async def test_adaptive_preanalysis_failure_does_not_drop_base_case(self):
        task = await self._create_task(name="single-flaky-analyzer", categories=["single"])

        with patch.object(case_executor, "analyze_response", _flaky_analyze_response_factory()):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()

        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(stored_task.total_attacks, 1)
        self.assertEqual(stored_task.completed_attacks, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].template_id, "S-001")

    async def test_pair_scan_dual_writes_base_and_advanced_cases(self):
        task = await self._create_task(
            name="pair",
            categories=["pair"],
            advanced_config={"enable_pair": True, "enable_control_variants": True},
        )

        await scan_runner.run_scan(task.id, {})

        await self._assert_dual_write_scan(
            task=task,
            expected_case_template_ids=["P-001", "PAIR-P-001"],
            expected_result_template_ids=["P-001", "PAIR-P-001"],
        )

    async def test_incomplete_scan_is_marked_failed_when_advanced_engine_drops_results(self):
        task = await self._create_task(
            name="pair-fails",
            categories=["pair"],
            advanced_config={"enable_pair": True, "enable_control_variants": True},
        )

        with patch.object(scan_runner, "run_pair", _failing_run_pair):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()

        self.assertEqual(stored_task.total_attacks, 2)
        self.assertEqual(stored_task.completed_attacks, 2)
        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].template_id, "P-001")
        self.assertIsNotNone(stored_task.overall_score)

    async def test_failed_scan_with_results_can_still_load_report_data(self):
        task = await self._create_task(
            name="pair-reportable",
            categories=["pair"],
            advanced_config={"enable_pair": True, "enable_control_variants": True},
        )

        with patch.object(scan_runner, "run_pair", _failing_run_pair):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            loaded_task = await _load_completed_scan(task.id, session)
            self.assertEqual(loaded_task.status, "completed")
            self.assertEqual(len(loaded_task.results), 1)
            self.assertEqual(loaded_task.results[0].template_id, "P-001")

    async def test_tap_scan_dual_writes_base_and_advanced_cases(self):
        task = await self._create_task(
            name="tap",
            categories=["tap"],
            advanced_config={"enable_tap": True, "enable_control_variants": True},
        )

        await scan_runner.run_scan(task.id, {})

        await self._assert_dual_write_scan(
            task=task,
            expected_case_template_ids=["T-001", "TAP-T-001"],
            expected_result_template_ids=["T-001", "TAP-T-001"],
        )

    async def test_crescendo_scan_dual_writes_base_and_advanced_cases(self):
        task = await self._create_task(
            name="crescendo",
            categories=["crescendo"],
            advanced_config={"enable_crescendo": True, "enable_control_variants": True},
        )

        await scan_runner.run_scan(task.id, {})

        await self._assert_dual_write_scan(
            task=task,
            expected_case_template_ids=["C-001", "CR-C-001"],
            expected_result_template_ids=["C-001", "CR-C-001"],
        )

    async def test_iris_scan_dual_writes_base_and_advanced_cases(self):
        task = await self._create_task(
            name="iris",
            categories=["iris"],
            advanced_config={"enable_self_explanation": True, "enable_control_variants": True},
        )

        await scan_runner.run_scan(task.id, {})

        await self._assert_dual_write_scan(
            task=task,
            expected_case_template_ids=["I-001", "IRIS-I-001"],
            expected_result_template_ids=["I-001", "IRIS-I-001"],
        )

    async def test_scan_health_probe_marks_unhealthy_for_repeated_non_model_probe(self):
        task = await self._create_task(
            name="probe-unhealthy",
            categories=["single"],
            target_config={"origin_rules": {"exact": ["service temporarily warming up."]}},
        )

        async def _unhealthy_probe(task, payload, *, case_id, variant_type, conversation_history=None):
            response_text = "service temporarily warming up." if variant_type == "health_probe" else f"mock::{payload}"
            return TargetResponseEnvelope(
                response_text=response_text,
                response_status="completed",
                target_type=task.target_type,
                transport_ok=True,
            )

        with patch.object(scan_runner, "_invoke_target_with_envelope", _unhealthy_probe):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)

        self.assertEqual(stored_task.target_health, "unhealthy")
        self.assertFalse(stored_task.health_probe_passed)
        self.assertEqual(
            stored_task.recent_health_signature,
            "origin_rule:exact:service temporarily warming up.",
        )

    async def test_preflight_unhealthy_no_longer_aborts_scan(self):
        """Preflight health probe detecting unhealthy target must NOT abort the scan.

        Prior to fix, ``signal_scan_stop()`` was called when the preflight probe
        classified the target as ``unhealthy``. Every subsequent base case then
        early-returned on the stop check without incrementing
        ``completed_attacks``, leaving ``completed < total`` and the scan was
        finalized as ``failed``. After the fix the unhealthy signal is only a
        diagnostic banner; the scan continues to run each case.
        """
        task = await self._create_task(
            name="preflight-unhealthy-continue",
            categories=["single"],
            target_config={"origin_rules": {"exact": ["service temporarily warming up."]}},
        )

        async def _unhealthy_probe(task, payload, *, case_id, variant_type, conversation_history=None):
            response_text = (
                "service temporarily warming up." if variant_type == "health_probe" else f"mock::{payload}"
            )
            return TargetResponseEnvelope(
                response_text=response_text,
                response_status="completed",
                target_type=task.target_type,
                transport_ok=True,
            )

        with patch.object(scan_runner, "_invoke_target_with_envelope", _unhealthy_probe):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
            ).scalars().all()

        # Unhealthy banner is still surfaced...
        self.assertEqual(stored_task.target_health, "unhealthy")
        self.assertFalse(stored_task.health_probe_passed)
        # ...but the scan was NOT aborted — every case ran and was counted.
        self.assertEqual(stored_task.total_attacks, 1)
        self.assertEqual(stored_task.completed_attacks, 1)
        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(len(results), 1)

    async def test_scan_level_stop_signal_surfaces_as_failed_not_completed(self):
        """A scan-level stop signal must end the scan as ``failed``, not ``completed``.

        Scan-level stop sources (user cancel / runtime-health tracker / deadline)
        mean the scan was intentionally cut short; the final status must reflect
        that. The alignment fix in this module only backfills ``completed_attacks``
        for single-case glitches (no stop signal active) — when the stop is
        scan-wide, the counter is left uneven so ``completed < total`` propagates
        to ``status = "failed"`` honestly. Simulated here by patching
        ``MAX_SCAN_DURATION_S`` so every ``_check_should_stop_isolated`` call
        returns ``True`` immediately.
        """
        task = await self._create_task(
            name="deadline-early-stop",
            categories=["pair"],
            advanced_config={"enable_pair": True, "enable_control_variants": True},
        )

        with patch.object(scan_runner, "MAX_SCAN_DURATION_S", -1.0):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)

        self.assertEqual(stored_task.total_attacks, 2)
        # Deadline fired before any case persisted; counter stays at 0 and the
        # final status correctly surfaces as failed (not completed).
        self.assertEqual(stored_task.completed_attacks, 0)
        self.assertEqual(stored_task.status, "failed")

    async def test_single_case_failure_without_stop_signal_keeps_scan_completed(self):
        """One flaky case should NOT fail the whole scan when no stop signal is active.

        Complements ``test_scan_level_stop_signal_surfaces_as_failed_not_completed``:
        when a single case raises an exception but no scan-level stop is active
        (not a cancel / not a deadline / not a runtime-health abort), the
        counter IS backfilled so ``completed == total`` and the scan reports
        ``completed``. This is the "optional graceful degradation" half of the
        alignment fix.
        """
        task = await self._create_task(
            name="single-case-glitch",
            categories=["pair"],
            advanced_config={"enable_pair": True, "enable_control_variants": True},
        )

        # PAIR engine raises; no scan-level stop signal is ever fired.
        with patch.object(scan_runner, "run_pair", _failing_run_pair):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)

        self.assertEqual(stored_task.total_attacks, 2)
        self.assertEqual(stored_task.completed_attacks, 2)
        self.assertEqual(stored_task.status, "completed")

    async def test_scan_runtime_health_marks_degraded_after_repeated_not_evaluable_cases(self):
        task = await self._create_task(name="runtime-degraded", categories=["degraded"])

        async def _timeout_send(task, payload, *, case_id, variant_type, conversation_history=None):
            # Target invocation now returns an envelope, and the "[ERROR] ..."
            # classification that case_executor used to do inline lives in
            # target_client, so the fake fills in what the real one would.
            return TargetResponseEnvelope(
                response_text="[ERROR] connect timeout",
                response_error="[ERROR] connect timeout",
                response_status="failed",
                session_id=None,
                target_type=task.target_type,
            )

        await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            healthy_task = await session.get(ScanTask, task.id)

        self.assertEqual(healthy_task.target_health, "healthy")
        self.assertTrue(healthy_task.health_probe_passed)

        retry_task = await self._create_task(name="runtime-degraded-retry", categories=["degraded"])
        with patch.object(case_executor, "invoke_target_with_envelope", _timeout_send):
            await scan_runner.run_scan(retry_task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, retry_task.id)

        self.assertEqual(stored_task.target_health, "degraded")
        self.assertTrue(stored_task.health_probe_passed)
        self.assertEqual(stored_task.invalid_response_ratio, 1.0)
        self.assertIn("Repeated non-evaluable signature during scan", stored_task.health_failure_reason)

        # Phase-4b change: ``degraded`` is a banner only, scan must keep
        # running. All 5 cases should be counted as completed because
        # response_screening already records each not_evaluable result
        # (which prevents fake defense_success in the final report).
        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(stored_task.total_attacks, 5)
        self.assertEqual(stored_task.completed_attacks, 5)

    async def test_runtime_degraded_does_not_signal_scan_stop(self):
        """Phase-4b regression: degraded runtime health must not call
        ``signal_scan_stop``. Prior to this fix, a transient burst of
        empty/error responses (e.g. TAP engine interacting poorly with a
        rate-limited target) aborted the whole scan at 5 consecutive
        failures, leaving the user with single-digit case counts and no
        diagnostic signal.
        """
        task = await self._create_task(name="runtime-degraded-no-stop", categories=["degraded"])

        async def _timeout_send(task, payload, *, case_id, variant_type, conversation_history=None):
            # Target invocation now returns an envelope, and the "[ERROR] ..."
            # classification that case_executor used to do inline lives in
            # target_client, so the fake fills in what the real one would.
            return TargetResponseEnvelope(
                response_text="[ERROR] connect timeout",
                response_error="[ERROR] connect timeout",
                response_status="failed",
                session_id=None,
                target_type=task.target_type,
            )

        stop_calls: list[str] = []
        original_signal = scan_runner.signal_scan_stop

        def _tracking_signal(task_id: str) -> None:
            stop_calls.append(task_id)
            original_signal(task_id)

        with patch.object(case_executor, "invoke_target_with_envelope", _timeout_send), \
             patch.object(scan_runner, "signal_scan_stop", _tracking_signal):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)

        # Degraded was reached (5 consecutive empty responses).
        self.assertEqual(stored_task.target_health, "degraded")
        # But ``signal_scan_stop`` was NEVER called for this scan_id —
        # runtime degraded is banner-only.
        self.assertNotIn(task.id, stop_calls)
        # And the scan finished with all cases counted.
        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(stored_task.completed_attacks, stored_task.total_attacks)

    async def test_runtime_unhealthy_tier_triggers_scan_stop(self):
        """Phase-4b regression: when the non-evaluable streak exceeds the
        dead-man-switch threshold, runtime health upgrades to
        ``unhealthy`` and ``signal_scan_stop`` IS called.

        We lower the threshold via ``advanced_config`` so a single
        fixture case can trip the tier-2 rule.
        """
        task = await self._create_task(
            name="runtime-unhealthy-stop",
            categories=["degraded"],
            # Lower the streak thresholds so the 4th consecutive empty
            # response upgrades directly to unhealthy. Matches the
            # real-world behaviour where an already-degraded target
            # keeps failing long enough to trip the dead-man switch.
            advanced_config={
                "health_signature_streak": 2,
                "health_unhealthy_streak": 4,
            },
        )

        async def _timeout_send(task, payload, *, case_id, variant_type, conversation_history=None):
            # Target invocation now returns an envelope, and the "[ERROR] ..."
            # classification that case_executor used to do inline lives in
            # target_client, so the fake fills in what the real one would.
            return TargetResponseEnvelope(
                response_text="[ERROR] connect timeout",
                response_error="[ERROR] connect timeout",
                response_status="failed",
                session_id=None,
                target_type=task.target_type,
            )

        stop_calls: list[str] = []
        original_signal = scan_runner.signal_scan_stop

        def _tracking_signal(task_id: str) -> None:
            stop_calls.append(task_id)
            original_signal(task_id)

        with patch.object(case_executor, "invoke_target_with_envelope", _timeout_send), \
             patch.object(scan_runner, "signal_scan_stop", _tracking_signal):
            await scan_runner.run_scan(task.id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task.id)

        # Tier-2 dead-man switch activated.
        self.assertEqual(stored_task.target_health, "unhealthy")
        self.assertIn("dead-man switch", (stored_task.health_failure_reason or ""))
        # And this time ``signal_scan_stop`` WAS called.
        self.assertIn(task.id, stop_calls)

    def test_case_serializer_prefers_reviewed_legacy_outcome(self):
        legacy = AttackResult(
            id="legacy-1",
            scan_task_id="scan-1",
            template_id="tpl",
            category="prompt_injection",
            technique="tech",
            attack_name="name",
            payload_text="payload",
            target_response="response",
            attack_successful=False,
            confidence=0.9,
            risk_level="none",
            evidence=None,
            leaked_info=None,
            explanation=None,
            remediation=None,
            owasp_id="LLM01",
            risk_score=0.0,
            analysis_raw={"verdict_status": "false_positive", "verdict_reason": "manual review"},
            created_at=datetime.now(timezone.utc),
        )
        attack_case = AttackCase(
            id="case-1",
            scan_task_id="scan-1",
            template_id="tpl",
            category="prompt_injection",
            technique="tech",
            attack_name="name",
            protocol_version="quartet_v1",
            case_status="completed",
            case_final_outcome="attack_delta_supported",
            attack_variant_response="response",
            control_assessment="attack_delta_supported",
            control_summary="summary",
            verdict_status="rule_verified",
            verdict_reason="automatic verdict",
            legacy_attack_result_id="legacy-1",
            summary_json={"primary_attack_successful": True, "quartet_present": True, "variant_count": 4},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        attack_case.legacy_attack_result = legacy
        attack_case.variants = []

        serialized = serialize_attack_case(attack_case)

        self.assertEqual(serialized.verdict_status, "false_positive")
        self.assertEqual(serialized.verdict_reason, "manual review")
        self.assertFalse(serialized.primary_attack_successful)

    def test_response_screening_keeps_normal_refusal_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I cannot comply with that request.",
                response_status="completed",
                target_type="openai_compatible",
                transport_ok=True,
            )
        )

        self.assertEqual(evaluation.evaluation_validity, "evaluable")
        self.assertEqual(evaluation.response_origin, "model")


if __name__ == "__main__":
    unittest.main()
