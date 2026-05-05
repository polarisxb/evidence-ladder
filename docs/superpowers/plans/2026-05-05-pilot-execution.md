# Stage 1.4 Pilot Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute Stage 1.3 prepared pilot suites through the existing scan runner, persist exact suite prompts and results, and provide a CLI entry point for executing a pending pilot `ScanTask`.

**Architecture:** Add a pilot suite mode to `backend/app/services/scan_runner.py` that detects `advanced_config.pilot_suite_path`, loads the validated Stage 1.3 `suite.json`, and runs only those logical cases. Add explicit quartet execution support in `backend/app/services/case_executor.py` so stored `AttackCaseVariant.request_text` values come directly from the suite instead of regenerated control prompts. Keep CSV and persisted `evidence_level` out of scope.

**Tech Stack:** Python 3, FastAPI service modules, SQLAlchemy async ORM, Pydantic v2 schemas, pytest/unittest async tests, existing `ScanTask`, `AttackCase`, `AttackResult`, and `AttackCaseVariant` models.

---

## Workspace Note

The user previously approved working directly in the main working directory instead of a git worktree. This plan therefore assumes commands run from `c:\all_project\ai-security`. Do not stage or commit unrelated existing `.cursor` or `.gitignore` changes.

## File Structure

- **Modify:** `backend/app/services/pilot_runner.py`
  - Normalize prepared OpenAI-compatible pilot tasks to use executable platform target URL `default` instead of `pilot-prepared`.

- **Modify:** `backend/tests/test_pilot_runner_scantask.py`
  - Add a regression test for the OpenAI-compatible executable target contract.

- **Modify:** `backend/app/services/case_executor.py`
  - Add explicit quartet variant construction and `prepare_explicit_case_attempt()`.

- **Create:** `backend/tests/test_pilot_case_executor.py`
  - Unit-test exact suite prompt execution order without touching the database.

- **Modify:** `backend/app/services/scan_runner.py`
  - Add pilot mode detection, suite validation, sequential pilot case execution, and pilot branch integration with existing status/scoring/broadcast lifecycle.

- **Create:** `backend/app/tests/test_pilot_suite_execution.py`
  - Integration-test pilot suite mode with an isolated SQLite database, deterministic mocked target calls, and exact persistence assertions.

- **Create:** `backend/app/scripts/execute_pilot.py`
  - Add a small CLI that executes an existing pending pilot `ScanTask` and prints final counters.

- **Create:** `backend/tests/test_execute_pilot_cli.py`
  - Smoke-test CLI parsing, DB initialization, `run_scan()` invocation, and summary output.

---

## Task 1: Normalize Prepared OpenAI-Compatible Pilot Targets

**Files:**
- Modify: `backend/tests/test_pilot_runner_scantask.py`
- Modify: `backend/app/services/pilot_runner.py`

- [ ] **Step 1: Write the failing target contract test**

Add this test to `backend/tests/test_pilot_runner_scantask.py` after `test_prepare_mode_creates_pending_scan_task`:

```python
async def test_prepare_openai_compatible_task_uses_platform_default_target(
    tmp_path: Path,
) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_openai",
        case_count=6,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    assert result.scan_task_id is not None

    async with async_session() as db:
        task = (
            await db.execute(select(ScanTask).where(ScanTask.id == result.scan_task_id))
        ).scalar_one()

    assert task.target_type == "openai_compatible"
    assert task.target_url == "default"
    assert task.target_config == {"model": "gpt-4o-mini"}
    assert task.advanced_config["pilot_model"] == "gpt-4o-mini"
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_scantask.py::test_prepare_openai_compatible_task_uses_platform_default_target -q
```

Expected result: FAIL because the current prepared task uses `target_url == "pilot-prepared"`.

- [ ] **Step 3: Implement target URL normalization**

In `backend/app/services/pilot_runner.py`, update `_create_pending_scan_task()` so `ScanTask.target_url` uses a helper:

```python
task = ScanTask(
    name=f"Pilot {suite_version} {run_id}",
    status="pending",
    target_url=_target_url_for_prepare(target_type),
    target_type=target_type,
    target_config=target_config,
    attack_categories=selected_categories,
    advanced_config={
        "quartet_mode": "full",
        "pilot_run_id": run_id,
        "pilot_suite_path": str(suite_path),
        "pilot_suite_hash": suite_hash,
        "pilot_case_count": selected_case_count,
        "pilot_variant_count": planned_variant_count,
        "pilot_seed": seed,
        "pilot_model": model,
    },
)
```

Add this helper below `_create_pending_scan_task()` and above `_target_config_for_prepare()`:

```python
def _target_url_for_prepare(target_type: str) -> str:
    if target_type == "builtin_vulnerable":
        return "builtin"
    if target_type == "openai_compatible":
        return "default"
    return "default"
```

Keep `_target_config_for_prepare()` unchanged:

```python
def _target_config_for_prepare(target_type: str, model: str) -> dict[str, Any] | None:
    if target_type == "builtin_vulnerable":
        return {"vulnerable_level": 2}
    return {"model": model}
```

- [ ] **Step 4: Verify pilot runner ScanTask tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_scantask.py -q
```

Expected result: all tests in `test_pilot_runner_scantask.py` pass.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add backend/app/services/pilot_runner.py backend/tests/test_pilot_runner_scantask.py
git commit -m "fix: make prepared pilot targets executable"
```

---

## Task 2: Add Explicit Quartet Case Execution Support

**Files:**
- Create: `backend/tests/test_pilot_case_executor.py`
- Modify: `backend/app/services/case_executor.py`

- [ ] **Step 1: Create the failing unit test file**

Create `backend/tests/test_pilot_case_executor.py` with this content:

```python
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.quartet import QuartetPrompts, QuartetVariantSet
from app.schemas.report import AnalysisResult
from app.services import case_executor

pytestmark = pytest.mark.anyio


def _suite_case() -> QuartetPrompts:
    return QuartetPrompts(
        case_id="TPL-001:0",
        category="prompt_injection",
        template_id="TPL-001",
        template_name="Pilot Template",
        owasp_id="LLM01",
        payload_language="en",
        payload_variant="seed",
        variants=QuartetVariantSet(
            attack="attack prompt from suite",
            clean="clean prompt from suite",
            quoted_attack="quoted prompt from suite",
            benign_distractor="benign prompt from suite",
        ),
    )


def _task() -> SimpleNamespace:
    return SimpleNamespace(
        id="scan-1",
        target_url="builtin",
        target_type="builtin_vulnerable",
        target_config={"vulnerable_level": 2},
        runtime_vars={},
        advanced_config={"skip_confirmation": True},
    )


async def test_prepare_explicit_case_attempt_uses_suite_prompts_in_stable_order(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, int, str]] = []

    async def fake_execute_case_variant(
        task,
        case_variant,
        *,
        conversation_history=None,
        case_id: str,
    ):
        calls.append(
            (
                case_id,
                str(case_variant["variant_type"]),
                int(case_variant["position"]),
                str(case_variant["request_text"]),
            )
        )
        return {
            **case_variant,
            "response_text": f"response::{case_variant['variant_type']}",
            "response_error": None,
            "response_status": "completed",
            "latency_ms": 1.0,
            "analysis_raw": {
                "response_evaluation": {"evaluation_validity": "evaluable"},
            },
            "response_evaluation": {"evaluation_validity": "evaluable"},
        }

    async def fake_analyze_case_variants(
        task,
        template,
        case_variants,
        *,
        attack_type: str | None = None,
        extra_context: str = "",
        skip_confirmation: bool = False,
    ):
        analysis = AnalysisResult(
            attack_successful=True,
            confidence=0.91,
            risk_level="high",
            evidence="mock evidence",
            leaked_info=None,
            explanation="mock explanation",
            remediation="mock remediation",
        )
        return {
            "case_variants": case_variants,
            "payload_text": case_variants[0]["request_text"],
            "target_response": case_variants[0]["response_text"],
            "analysis": analysis,
            "risk_score": 7.0,
            "verdict": {
                "verdict_status": "rule_verified",
                "verdict_reason": "mock verdict",
                "rule_hits": [{"rule": "mock_rule", "evidence": "mock_evidence"}],
            },
            "control_results": [
                {
                    "variant": str(variant["variant_type"]),
                    "prompt": str(variant["request_text"]),
                    "response": str(variant["response_text"]),
                }
                for variant in case_variants
                if variant["variant_type"] != "attack"
            ],
            "control_summary": {
                "control_assessment": "attack_delta_supported",
                "control_summary": "mock control summary",
            },
            "response_evaluation": {"evaluation_validity": "evaluable"},
            "case_summary": {
                "protocol_version": "quartet_v1",
                "quartet_present": True,
                "variant_count": 4,
                "primary_attack_successful": True,
                "case_final_outcome": "rule_verified_finding",
                "control_assessment": "attack_delta_supported",
                "control_summary": "mock control summary",
                "verdict_status": "rule_verified",
                "verdict_reason": "mock verdict",
                "response_evaluation": {"evaluation_validity": "evaluable"},
            },
        }

    async def fake_apply_business_verification(task, case_attempt, ws_clients=None):
        return case_attempt

    monkeypatch.setattr(case_executor, "execute_case_variant", fake_execute_case_variant)
    monkeypatch.setattr(case_executor, "analyze_case_variants", fake_analyze_case_variants)
    monkeypatch.setattr(case_executor, "apply_business_verification", fake_apply_business_verification)

    template = {
        "id": "TPL-001",
        "name": "Pilot Template",
        "category": "prompt_injection",
        "category_name": "prompt_injection",
        "owasp_id": "LLM01",
        "technique": "pilot_suite",
    }

    result = await case_executor.prepare_explicit_case_attempt(
        _task(),
        template,
        _suite_case(),
    )

    assert result["case_id"] == "TPL-001:0"
    assert result["payload_text"] == "attack prompt from suite"
    assert [variant["variant_type"] for variant in result["case_variants"]] == [
        "attack",
        "clean",
        "quoted_attack",
        "benign_distractor",
    ]
    assert calls == [
        ("TPL-001:0", "attack", 0, "attack prompt from suite"),
        ("TPL-001:0", "clean", 1, "clean prompt from suite"),
        ("TPL-001:0", "quoted_attack", 2, "quoted prompt from suite"),
        ("TPL-001:0", "benign_distractor", 3, "benign prompt from suite"),
    ]
```

- [ ] **Step 2: Run the failing unit test**

Run:

```powershell
python -m pytest backend\tests\test_pilot_case_executor.py -q
```

Expected result: FAIL with `AttributeError` because `prepare_explicit_case_attempt` does not exist.

- [ ] **Step 3: Implement explicit quartet helpers**

In `backend/app/services/case_executor.py`, add this constant after `logger = logging.getLogger(__name__)`:

```python
EXPLICIT_QUARTET_VARIANT_ORDER: tuple[str, ...] = (
    "attack",
    "clean",
    "quoted_attack",
    "benign_distractor",
)
```

Add this function near `build_case_variants()`:

```python
def build_explicit_case_variants(suite_case) -> list[dict]:
    variants = suite_case.variants
    case_variants: list[dict] = []
    for position, variant_type in enumerate(EXPLICIT_QUARTET_VARIANT_ORDER):
        request_text = str(getattr(variants, variant_type) or "")
        case_variants.append(
            {
                "variant_type": variant_type,
                "position": position,
                "request_text": request_text,
                "response_text": None,
                "response_error": None,
                "response_status": "pending",
                "latency_ms": None,
                "analysis_raw": None,
                "is_primary": variant_type == "attack",
            }
        )
    return case_variants
```

Add this async function after `prepare_case_attempt()`:

```python
async def prepare_explicit_case_attempt(
    task,
    template: dict,
    suite_case,
    *,
    ws_clients: dict[str, list[WebSocket]] | None = None,
) -> dict:
    case_id = str(suite_case.case_id)
    completed_variants: list[dict] = []
    for case_variant in build_explicit_case_variants(suite_case):
        completed_variants.append(
            await execute_case_variant(task, case_variant, case_id=case_id)
        )

    skip_confirmation = bool(
        (getattr(task, "advanced_config", None) or {}).get("skip_confirmation", False)
    )
    analyzed = await analyze_case_variants(
        task,
        template,
        completed_variants,
        attack_type=template.get("category_name", template.get("category", "")),
        extra_context="Pilot suite explicit quartet execution.",
        skip_confirmation=skip_confirmation,
    )
    analyzed["case_id"] = case_id
    analyzed["probe_session_id"] = None
    return await apply_business_verification(task, analyzed, ws_clients=ws_clients)
```

- [ ] **Step 4: Verify explicit quartet helper tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_case_executor.py -q
```

Expected result: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add backend/app/services/case_executor.py backend/tests/test_pilot_case_executor.py
git commit -m "feat: execute explicit pilot quartet prompts"
```

---

## Task 3: Add Pilot Suite Mode to Scan Runner

**Files:**
- Create: `backend/app/tests/test_pilot_suite_execution.py`
- Modify: `backend/app/services/scan_runner.py`

- [ ] **Step 1: Create the failing integration test file**

Create `backend/app/tests/test_pilot_suite_execution.py` with this content:

```python
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
```

- [ ] **Step 2: Run the failing integration tests**

Run:

```powershell
python -m pytest backend\app\tests\test_pilot_suite_execution.py -q
```

Expected result: FAIL because `run_scan()` still expands templates through `AttackEngine.get_all_templates()` and does not load `pilot_suite_path`.

- [ ] **Step 3: Import pilot helpers in scan runner**

In `backend/app/services/scan_runner.py`, add `Path` to imports near the top:

```python
from pathlib import Path
```

Update the `case_executor` import block to include the new helper:

```python
from app.services.case_executor import (
    prepare_case_attempt as _prepare_case_attempt,
    prepare_explicit_case_attempt as _prepare_explicit_case_attempt,
    matched_probe_session_id as _matched_probe_session_id,
    build_attack_objective as _build_attack_objective,
    envelope_to_variant_transport_meta as _envelope_to_variant_transport_meta,
)
```

Add the quartet suite import near other service imports:

```python
from app.services.quartet_generator import load_suite
```

- [ ] **Step 4: Add pilot suite helper functions**

In `backend/app/services/scan_runner.py`, add these helpers above `_run_base_templates()`:

```python
_REQUIRED_PILOT_VARIANTS: tuple[str, ...] = (
    "attack",
    "clean",
    "quoted_attack",
    "benign_distractor",
)


def _pilot_suite_path_from_config(advanced_config: dict) -> str | None:
    value = advanced_config.get("pilot_suite_path")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _load_validated_pilot_suite(advanced_config: dict):
    suite_path = _pilot_suite_path_from_config(advanced_config)
    if suite_path is None:
        raise ValueError("pilot_suite_path is required for pilot suite execution")

    suite = load_suite(Path(suite_path))
    expected_hash = str(advanced_config.get("pilot_suite_hash") or "").strip()
    if expected_hash and expected_hash != suite.manifest.content_hash:
        raise ValueError("pilot suite hash does not match ScanTask advanced_config")

    expected_case_count = advanced_config.get("pilot_case_count")
    if expected_case_count is not None and int(expected_case_count) != suite.manifest.case_count:
        raise ValueError("pilot case count does not match suite manifest")

    expected_variant_count = advanced_config.get("pilot_variant_count")
    if expected_variant_count is not None and int(expected_variant_count) != suite.manifest.case_count * 4:
        raise ValueError("pilot variant count does not match suite manifest")

    for suite_case in suite.cases:
        for variant_type in _REQUIRED_PILOT_VARIANTS:
            prompt = str(getattr(suite_case.variants, variant_type) or "")
            if not prompt.strip():
                raise ValueError(
                    f"pilot suite case {suite_case.case_id} is missing {variant_type} prompt"
                )
    return suite


def _template_from_pilot_case(suite_case) -> dict:
    template_id = str(suite_case.template_id or suite_case.case_id)
    template_name = str(suite_case.template_name or f"Pilot case {suite_case.case_id}")
    return {
        "id": template_id,
        "name": template_name,
        "category": suite_case.category,
        "category_name": suite_case.category,
        "owasp_id": suite_case.owasp_id or "",
        "technique": "pilot_suite",
    }
```

- [ ] **Step 5: Add sequential pilot case execution**

In `backend/app/services/scan_runner.py`, add this helper below `_run_base_templates()`:

```python
async def _run_pilot_suite_cases(
    task_id: str,
    task,
    suite,
    ws_clients: dict,
    *,
    scan_deadline: float,
) -> None:
    for suite_case in suite.cases:
        if await _check_should_stop_isolated(task_id, scan_deadline):
            return

        tpl = _template_from_pilot_case(suite_case)
        persisted = False
        await _broadcast(ws_clients, task_id, {
            "type": "attack_started",
            "template_id": tpl["id"],
            "attack_name": tpl["name"],
            "category": tpl.get("category", ""),
        })
        try:
            case_attempt = await _prepare_explicit_case_attempt(
                task,
                tpl,
                suite_case,
                ws_clients=ws_clients,
            )
            analysis = case_attempt["analysis"]
            completed, vulns, total = await _persist_and_count(
                task_id,
                task,
                tpl,
                case_attempt,
                analysis,
            )
            persisted = True
            await _observe_case_response_health(task_id, case_attempt, ws_clients)
            await _broadcast(ws_clients, task_id, {
                "type": "attack_completed",
                "template_id": tpl["id"],
                "attack_name": tpl["name"],
                "successful": analysis.attack_successful,
                "risk_level": analysis.risk_level,
                "completed": completed,
                "total": total,
                "vulnerabilities_found": vulns,
            })
        except Exception as exc:
            logger.warning("Pilot suite case failed %s: %s", tpl["id"], exc)
        finally:
            if not persisted and not await _check_should_stop_isolated(task_id, scan_deadline):
                await _increment_completed(task_id)
                await _broadcast(ws_clients, task_id, {
                    "type": "attack_completed",
                    "template_id": tpl["id"],
                    "attack_name": tpl["name"],
                    "skipped": True,
                })
```

- [ ] **Step 6: Integrate pilot mode in `run_scan()`**

In `backend/app/services/scan_runner.py`, change the beginning of `run_scan()` after `_apply_scan_providers(task)` so it detects pilot mode before expanding templates:

```python
adv = task.advanced_config or {}
pilot_suite_path = _pilot_suite_path_from_config(adv)
pilot_suite = None

if pilot_suite_path:
    templates = []
    enable_mutations = False
else:
    engine = AttackEngine()
    templates = engine.get_all_templates(task.attack_categories)
    enable_mutations = adv.get("enable_mutations", False)
```

Keep the existing advanced option assignments after this block:

```python
quartet_mode = adv.get("quartet_mode") or (
    "adaptive" if adv.get("enable_control_variants", True) else "off"
)
enable_crescendo = adv.get("enable_crescendo", False)
enable_fitd = adv.get("enable_fitd", False)
enable_msj = adv.get("enable_msj", False)
enable_ice = adv.get("enable_ice", False)
enable_tap = adv.get("enable_tap", False)
enable_pair = adv.get("enable_pair", False)
enable_self_explanation = adv.get("enable_self_explanation", False)
parallel_attacks = max(1, adv.get("parallel_attacks", 3))
```

Before total calculation, disable expansion features for pilot mode:

```python
if pilot_suite_path:
    enable_crescendo = False
    enable_fitd = False
    enable_msj = False
    enable_ice = False
    enable_tap = False
    enable_pair = False
    enable_self_explanation = False
```

Replace total calculation with a pilot branch:

```python
if pilot_suite_path:
    task.total_attacks = int(adv.get("pilot_case_count") or 0)
else:
    base_attack_total = sum(_count_base_template_cases(t) for t in templates)
    templates_with_payload = sum(
        1 for t in templates
        if t.get("payloads") and t["payloads"][0].get("text")
    )
    advanced_attack_total = 0
    if enable_pair:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_self_explanation:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_crescendo:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_fitd:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_msj:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_ice:
        advanced_attack_total += min(5, templates_with_payload)
    if enable_tap:
        advanced_attack_total += min(5, templates_with_payload)
    task.total_attacks = base_attack_total + advanced_attack_total
```

Inside the existing execution `try:` block, before target health probing, load and validate the suite:

```python
if pilot_suite_path:
    pilot_suite = _load_validated_pilot_suite(adv)
    task.total_attacks = pilot_suite.manifest.case_count
    await db.commit()
```

Replace the initial `all_coros` construction with a pilot branch:

```python
if pilot_suite is not None:
    await _run_pilot_suite_cases(
        task_id,
        task,
        pilot_suite,
        ws_clients,
        scan_deadline=scan_deadline,
    )
    gather_results = []
else:
    all_coros: list[Coroutine] = [
        _run_base_templates(
            task_id, task, templates, ws_clients,
            quartet_mode=quartet_mode,
            scan_deadline=scan_deadline,
            base_sem=base_sem,
        )
    ]
    if enable_pair:
        all_coros.append(_run_advanced_pair(
            task_id, task, templates, ws_clients,
            adv.get("pair_max_rounds", 20),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_self_explanation:
        all_coros.append(_run_advanced_self_explanation(
            task_id, task, templates, ws_clients,
            adv.get("self_explanation_rounds", 5),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_crescendo:
        all_coros.append(_run_advanced_crescendo(
            task_id, task, templates, ws_clients,
            adv.get("crescendo_max_turns", 10),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_fitd:
        all_coros.append(_run_advanced_fitd(
            task_id, task, templates, ws_clients,
            adv.get("fitd_num_levels", 6),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_msj:
        all_coros.append(_run_advanced_msj(
            task_id, task, templates, ws_clients,
            adv.get("msj_shot_count", 32),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_ice:
        all_coros.append(_run_advanced_ice(
            task_id, task, templates, ws_clients,
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))
    if enable_tap:
        all_coros.append(_run_advanced_tap(
            task_id, task, templates, ws_clients,
            adv.get("tap_branching_factor", 4),
            adv.get("tap_max_depth", 10),
            quartet_mode=quartet_mode,
            should_stop=parallel_should_stop,
            chain_sem=chain_sem,
        ))

    gather_results = await asyncio.gather(*all_coros, return_exceptions=True)
```

Keep the existing loop that logs exceptions from `gather_results`.

- [ ] **Step 7: Verify pilot suite integration tests**

Run:

```powershell
python -m pytest backend\app\tests\test_pilot_suite_execution.py -q
```

Expected result: PASS.

- [ ] **Step 8: Verify existing scan runner regressions**

Run:

```powershell
python -m pytest backend\app\tests\test_phase1_regression.py backend\app\tests\test_phase2_adapter_regression.py backend\app\tests\test_phase3_probe_regression.py -q
```

Expected result: PASS.

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add backend/app/services/scan_runner.py backend/app/tests/test_pilot_suite_execution.py
git commit -m "feat: execute pilot suites through scan runner"
```

---

## Task 4: Add `execute_pilot.py` CLI

**Files:**
- Create: `backend/app/scripts/execute_pilot.py`
- Create: `backend/tests/test_execute_pilot_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `backend/tests/test_execute_pilot_cli.py` with this content:

```python
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.scripts import execute_pilot


def test_execute_pilot_cli_requires_scan_task_id() -> None:
    with pytest.raises(SystemExit) as exc_info:
        execute_pilot.main([])

    assert exc_info.value.code == 2


def test_execute_pilot_cli_runs_scan_and_prints_summary(monkeypatch, capsys) -> None:
    calls: list[object] = []

    async def fake_init_db() -> None:
        calls.append("init_db")

    async def fake_run_scan(scan_task_id: str, ws_clients: dict) -> None:
        calls.append(("run_scan", scan_task_id, ws_clients))

    async def fake_load_scan_task(scan_task_id: str):
        calls.append(("load", scan_task_id))
        return SimpleNamespace(
            id=scan_task_id,
            status="completed",
            completed_attacks=30,
            total_attacks=30,
            vulnerabilities_found=4,
            overall_score=7.25,
        )

    monkeypatch.setattr(execute_pilot, "init_db", fake_init_db)
    monkeypatch.setattr(execute_pilot, "run_scan", fake_run_scan)
    monkeypatch.setattr(execute_pilot, "_load_scan_task", fake_load_scan_task)

    execute_pilot.main(["--scan-task-id", "scan-123"])

    assert calls == [
        "init_db",
        ("run_scan", "scan-123", {}),
        ("load", "scan-123"),
    ]
    captured = capsys.readouterr().out
    assert "scan_task_id=scan-123" in captured
    assert "status=completed" in captured
    assert "completed_attacks=30" in captured
    assert "total_attacks=30" in captured
    assert "vulnerabilities_found=4" in captured
    assert "overall_score=7.25" in captured
```

- [ ] **Step 2: Run the failing CLI tests**

Run:

```powershell
python -m pytest backend\tests\test_execute_pilot_cli.py -q
```

Expected result: FAIL because `app.scripts.execute_pilot` does not exist.

- [ ] **Step 3: Implement the CLI script**

Create `backend/app/scripts/execute_pilot.py` with this content:

```python
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from app.database import async_session, init_db
from app.models import ScanTask
from app.services.scan_runner import run_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a prepared Stage 1 pilot scan.")
    parser.add_argument("--scan-task-id", required=True)
    return parser


async def _load_scan_task(scan_task_id: str) -> ScanTask | None:
    async with async_session() as db:
        return await db.get(ScanTask, scan_task_id)


async def _run(args: argparse.Namespace) -> ScanTask:
    await init_db()
    await run_scan(args.scan_task_id, {})
    task = await _load_scan_task(args.scan_task_id)
    if task is None:
        raise SystemExit(f"scan_task_id={args.scan_task_id} was not found after execution")
    return task


def _format_summary(task: ScanTask) -> str:
    return "\n".join(
        [
            f"scan_task_id={task.id}",
            f"status={task.status}",
            f"completed_attacks={task.completed_attacks}",
            f"total_attacks={task.total_attacks}",
            f"vulnerabilities_found={task.vulnerabilities_found}",
            f"overall_score={task.overall_score}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    task = asyncio.run(_run(args))
    print(_format_summary(task))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify CLI tests**

Run:

```powershell
python -m pytest backend\tests\test_execute_pilot_cli.py -q
```

Expected result: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add backend/app/scripts/execute_pilot.py backend/tests/test_execute_pilot_cli.py
git commit -m "feat: add pilot execution cli"
```

---

## Task 5: Final Verification and Manual Smoke Documentation

**Files:**
- Modify only files changed by Tasks 1 through 4 if verification reveals implementation mistakes.

- [ ] **Step 1: Run targeted Stage 1.4 tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_scantask.py backend\tests\test_pilot_case_executor.py backend\app\tests\test_pilot_suite_execution.py backend\tests\test_execute_pilot_cli.py -q
```

Expected result: PASS.

- [ ] **Step 2: Run scan runner regression tests**

Run:

```powershell
python -m pytest backend\app\tests\test_phase1_regression.py backend\app\tests\test_phase2_adapter_regression.py backend\app\tests\test_phase3_probe_regression.py -q
```

Expected result: PASS.

- [ ] **Step 3: Run syntax verification**

Run:

```powershell
python -m compileall -q backend\app
```

Expected result: exit code 0.

- [ ] **Step 4: Run full backend test suite when time allows**

Run:

```powershell
python -m pytest backend\tests backend\app\tests -q
```

Expected result: PASS or only pre-existing unrelated failures documented with exact failing test names.

- [ ] **Step 5: Check staged and unstaged changes**

Run:

```powershell
git status --short
git diff --check
```

Expected result: `git diff --check` exits 0. `git status --short` may still show pre-existing unrelated `.cursor` and `.gitignore` changes; do not stage those unless the user explicitly asks.

- [ ] **Step 6: Commit verification fixes if any were needed**

If Task 5 required code fixes, stage only Stage 1.4 files and run:

```powershell
git add backend/app/services/pilot_runner.py backend/app/services/case_executor.py backend/app/services/scan_runner.py backend/app/scripts/execute_pilot.py backend/tests/test_pilot_runner_scantask.py backend/tests/test_pilot_case_executor.py backend/tests/test_execute_pilot_cli.py backend/app/tests/test_pilot_suite_execution.py
git commit -m "fix: stabilize pilot suite execution"
```

If Task 5 required no code fixes, do not create an empty commit.

---

## Self-Review Checklist

- **Spec coverage:**
  - Dual-track acceptance is covered by mocked/builtin automated tests and CLI manual execution path.
  - CSV export remains excluded.
  - `scan_runner` remains the execution path.
  - Exact `suite.json` prompt persistence is tested through `AttackCaseVariant.request_text` assertions.
  - OpenAI-compatible target normalization is covered by `test_prepare_openai_compatible_task_uses_platform_default_target`.
  - Evidence level remains derived because no model/schema migration is planned.

- **Risk coverage:**
  - Accidental template expansion is blocked by patching `AttackEngine.get_all_templates` to raise during pilot suite tests.
  - Prompt drift is blocked by exact stored prompt assertions.
  - Hash mismatch is tested to fail before persistence.
  - Advanced engine expansion is neutralized by pilot branch disabling expansion flags.

- **Type consistency:**
  - `prepare_explicit_case_attempt()` accepts the Pydantic `QuartetPrompts` object returned by `load_suite()`.
  - `suite_case.variants.attack`, `suite_case.variants.clean`, `suite_case.variants.quoted_attack`, and `suite_case.variants.benign_distractor` match `backend/app/schemas/quartet.py`.
  - `ScanTask.total_attacks` and `completed_attacks` count logical cases.
  - `AttackCaseVariant` row count is four times the logical case count.
