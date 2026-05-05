from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AttackCase, AttackCaseVariant, AttackResult, ScanTask
from app.schemas.quartet import QuartetPrompts, QuartetVariantSet
from app.schemas.report import AnalysisResult
from app.services import case_executor, scan_runner
from app.services.attack_engine import AttackEngine
from app.services.quartet_generator import dump_suite
from app.services.response_screening import TargetResponseEnvelope


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass


async def _fake_send_to_target(payload, target_url, target_type, target_config, conversation_history=None):
    return f"mock-response::{payload}"


async def _fake_invoke_target_with_envelope(task, payload, *, case_id, variant_type, conversation_history=None):
    return TargetResponseEnvelope(
        response_text=f"probe-response::{payload}",
        response_status="completed",
        target_type=task.target_type,
        transport_ok=True,
    )


async def _fake_analyze_response(attack_type, attack_payload, target_response, context="", *, skip_confirmation=False):
    return AnalysisResult(
        attack_successful=True,
        confidence=0.91,
        risk_level="high",
        evidence="mock evidence",
        leaked_info=None,
        explanation="mock explanation",
        remediation="mock remediation",
    )


def _fake_classify_verdict(*, attack_payload, target_response, analysis, target_config, control_assessment=None):
    return {
        "verdict_status": "rule_verified",
        "verdict_reason": "mock verdict",
        "rule_hits": [{"rule": "mock_rule", "evidence": "mock_evidence"}],
    }


def _fake_summarize_control_comparison(*, attack_response, control_results, analysis, target_config=None):
    return {
        "control_assessment": "attack_delta_supported",
        "control_summary": "mock control summary",
    }


def _forbid_template_expansion(self, categories=None):
    raise AssertionError("Pilot suite mode must not expand attack categories")


class PilotSuiteExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
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
            patch.object(case_executor, "send_to_target", _fake_send_to_target),
            patch.object(case_executor, "analyze_response", _fake_analyze_response),
            patch.object(case_executor, "classify_verdict", _fake_classify_verdict),
            patch.object(case_executor, "summarize_control_comparison", _fake_summarize_control_comparison),
            patch.object(scan_runner, "_invoke_target_with_envelope", _fake_invoke_target_with_envelope),
            patch.object(AttackEngine, "get_all_templates", _forbid_template_expansion),
        ]
        for patcher in self.patchers:
            patcher.start()

    async def asyncTearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        await self.engine.dispose()
        _safe_unlink(self.db_path)

    def _write_suite(self, root: Path):
        suite_path = root / "suite.json"
        manifest = dump_suite(
            [
                QuartetPrompts(
                    case_id="PILOT-001:0",
                    category="prompt_injection",
                    template_id="PILOT-001",
                    template_name="Pilot One",
                    owasp_id="LLM01",
                    variants=QuartetVariantSet(
                        attack="attack prompt one",
                        clean="clean prompt one",
                        quoted_attack="quoted prompt one",
                        benign_distractor="benign prompt one",
                    ),
                ),
                QuartetPrompts(
                    case_id="PILOT-002:0",
                    category="jailbreak",
                    template_id="PILOT-002",
                    template_name="Pilot Two",
                    owasp_id="LLM02",
                    variants=QuartetVariantSet(
                        attack="attack prompt two",
                        clean="clean prompt two",
                        quoted_attack="quoted prompt two",
                        benign_distractor="benign prompt two",
                    ),
                ),
            ],
            out_path=suite_path,
            suite_version="v0.1",
            description="pilot execution test",
        )
        return suite_path, manifest

    async def _create_pilot_task(self, suite_path: Path, suite_hash: str) -> ScanTask:
        async with self.session_factory() as session:
            task = ScanTask(
                name="Pilot execution fixture",
                status="pending",
                target_url="builtin",
                target_type="builtin_vulnerable",
                target_config={"vulnerable_level": 2},
                attack_categories=["prompt_injection", "jailbreak"],
                advanced_config={
                    "quartet_mode": "full",
                    "pilot_run_id": "fixture_run",
                    "pilot_suite_path": str(suite_path),
                    "pilot_suite_hash": suite_hash,
                    "pilot_case_count": 2,
                    "pilot_variant_count": 8,
                    "pilot_seed": 20260504,
                    "pilot_model": "gpt-4o-mini",
                    "enable_pair": True,
                    "enable_mutations": True,
                },
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def test_pilot_suite_mode_persists_exact_suite_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path, manifest = self._write_suite(Path(tmp))
            task = await self._create_pilot_task(suite_path, manifest.content_hash)

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
                        select(AttackCaseVariant)
                        .join(AttackCase)
                        .where(AttackCase.scan_task_id == task.id)
                        .order_by(AttackCaseVariant.request_text)
                    )
                ).scalars().all()

        self.assertEqual(stored_task.status, "completed")
        self.assertEqual(stored_task.total_attacks, 2)
        self.assertEqual(stored_task.completed_attacks, 2)
        self.assertEqual(len(cases), 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(variants), 8)
        self.assertEqual(
            sorted(variant.request_text for variant in variants),
            sorted(
                [
                    "attack prompt one",
                    "clean prompt one",
                    "quoted prompt one",
                    "benign prompt one",
                    "attack prompt two",
                    "clean prompt two",
                    "quoted prompt two",
                    "benign prompt two",
                ]
            ),
        )
        self.assertEqual(
            sorted(result.template_id for result in results),
            ["PILOT-001", "PILOT-002"],
        )

    async def test_pilot_suite_hash_mismatch_fails_before_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path, manifest = self._write_suite(Path(tmp))
            task = await self._create_pilot_task(suite_path, "0" * len(manifest.content_hash))

            await scan_runner.run_scan(task.id, {})

            async with self.session_factory() as session:
                stored_task = await session.get(ScanTask, task.id)
                cases = (
                    await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task.id))
                ).scalars().all()
                results = (
                    await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task.id))
                ).scalars().all()

        self.assertEqual(stored_task.status, "failed")
        self.assertEqual(len(cases), 0)
        self.assertEqual(len(results), 0)
