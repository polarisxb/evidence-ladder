# Stage 1.3 Pilot Runner CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic Stage 1.3 Pilot Runner CLI that selects 30 logical cases, generates quartet suite artifacts, and optionally creates a pending `ScanTask` without running models.

**Architecture:** Put reusable logic in `backend/app/services/pilot_runner.py` and keep `backend/app/scripts/run_pilot.py` as a thin argparse wrapper. The service loads attack templates, selects logical cases, calls the Stage 1.2 quartet generator, writes `config.json`/`suite.json`/`summary.json`, and creates a pending DB task only when not in dry-run mode.

**Tech Stack:** Python 3.13, argparse, dataclasses, pathlib/json, Pydantic quartet schemas, SQLAlchemy async session, pytest/anyio.

---

## File Structure

- Create: `backend/app/services/pilot_runner.py`
  - Owns case selection, artifact writing, and optional pending `ScanTask` creation.
  - Must not import or call `scan_runner.run_scan`.
- Create: `backend/app/scripts/run_pilot.py`
  - Thin CLI wrapper around `prepare_pilot_run`.
  - Calls `init_db()` only for non-dry-run mode.
- Create: `backend/tests/test_pilot_runner_selector.py`
  - Unit tests for deterministic case selection.
- Create: `backend/tests/test_pilot_runner_artifacts.py`
  - Unit tests for dry-run artifacts and suite integrity.
- Create: `backend/tests/test_pilot_runner_scantask.py`
  - Async tests for pending `ScanTask` preparation.
- Create: `backend/tests/test_run_pilot_cli.py`
  - CLI wrapper smoke test using dry-run mode.

---

### Task 1: Case Selector

**Files:**
- Create: `backend/tests/test_pilot_runner_selector.py`
- Create: `backend/app/services/pilot_runner.py`

- [ ] **Step 1: Write failing selector tests**

Create `backend/tests/test_pilot_runner_selector.py`:

```python
from __future__ import annotations

from collections import Counter

import pytest

from app.services.pilot_runner import (
    PREFERRED_PILOT_CATEGORIES,
    load_attack_template_bundles,
    select_pilot_cases,
)


def test_default_selector_returns_30_cases_balanced_across_six_categories() -> None:
    bundles = load_attack_template_bundles()

    cases = select_pilot_cases(bundles, case_count=30, seed=20260504)

    assert len(cases) == 30
    counts = Counter(case.category for case in cases)
    assert list(counts) == list(PREFERRED_PILOT_CATEGORIES)
    assert counts == {category: 5 for category in PREFERRED_PILOT_CATEGORIES}


def test_selector_uses_stable_case_ids_and_payload_indexes() -> None:
    bundles = load_attack_template_bundles()

    cases = select_pilot_cases(bundles, case_count=6, seed=20260504)

    assert [case.case_id for case in cases] == [
        "PI-001:0",
        "SP-001:0",
        "JB-001:0",
        "ID-001:0",
        "II-001:0",
        "EA-001:0",
    ]
    assert [case.payload_index for case in cases] == [0, 0, 0, 0, 0, 0]


def test_selector_is_deterministic_for_same_input_and_seed() -> None:
    bundles = load_attack_template_bundles()

    first = select_pilot_cases(bundles, case_count=30, seed=20260504)
    second = select_pilot_cases(bundles, case_count=30, seed=20260504)

    assert first == second


def test_selector_rejects_unsatisfied_case_count() -> None:
    bundles = [
        {
            "category": "prompt_injection",
            "owasp_id": "LLM01",
            "templates": [
                {
                    "id": "PI-X",
                    "name": "Tiny fixture",
                    "payloads": [
                        {"text": "one", "language": "en", "variant": "base"},
                    ],
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="requested case count"):
        select_pilot_cases(bundles, case_count=2, seed=20260504)
```

- [ ] **Step 2: Run selector tests and verify RED**

Run from repo root:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `app.services.pilot_runner`.

- [ ] **Step 3: Implement minimal selector service**

Create `backend/app/services/pilot_runner.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PREFERRED_PILOT_CATEGORIES: tuple[str, ...] = (
    "prompt_injection",
    "system_prompt_extraction",
    "jailbreak",
    "information_disclosure",
    "indirect_injection",
    "excessive_agency",
)

DEFAULT_PILOT_SEED = 20260504
DEFAULT_CASE_COUNT = 30
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_SUITE_VERSION = "v0.1"

ATTACK_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "attack_templates"


@dataclass(frozen=True)
class PilotCase:
    case_id: str
    category: str
    owasp_id: str | None
    template_id: str
    template_name: str | None
    payload_index: int
    payload_text: str
    payload_language: str | None
    payload_variant: str | None


def load_attack_template_bundles(templates_dir: Path | None = None) -> list[dict[str, Any]]:
    root = Path(templates_dir) if templates_dir is not None else ATTACK_TEMPLATES_DIR
    paths = sorted(root.glob("*.json"))
    if not paths:
        raise ValueError(f"No attack template files found in {root}")
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def select_pilot_cases(
    bundles: Sequence[Mapping[str, Any]],
    *,
    case_count: int = DEFAULT_CASE_COUNT,
    seed: int = DEFAULT_PILOT_SEED,
    categories: Sequence[str] = PREFERRED_PILOT_CATEGORIES,
) -> list[PilotCase]:
    if case_count <= 0:
        raise ValueError("requested case count must be positive")

    buckets: dict[str, list[PilotCase]] = {category: [] for category in categories}
    overflow: list[PilotCase] = []

    for bundle in bundles:
        category = str(bundle.get("category") or "").strip()
        cases = _cases_from_bundle(bundle)
        if category in buckets:
            buckets[category].extend(cases)
        else:
            overflow.extend(cases)

    preferred = [category for category in categories if buckets.get(category)]
    if not preferred:
        raise ValueError("No eligible payloads found for pilot selection")

    base_quota = case_count // len(preferred)
    remainder = case_count % len(preferred)
    selected: list[PilotCase] = []
    selected_keys: set[tuple[str, str]] = set()

    for index, category in enumerate(preferred):
        quota = base_quota + (1 if index < remainder else 0)
        for case in buckets[category][:quota]:
            selected.append(case)
            selected_keys.add((case.category, case.case_id))

    if len(selected) < case_count:
        all_cases: list[PilotCase] = []
        for category in preferred:
            all_cases.extend(buckets[category])
        all_cases.extend(overflow)
        for case in all_cases:
            key = (case.category, case.case_id)
            if key in selected_keys:
                continue
            selected.append(case)
            selected_keys.add(key)
            if len(selected) == case_count:
                break

    if len(selected) != case_count:
        raise ValueError(
            f"requested case count {case_count} cannot be satisfied; "
            f"only selected {len(selected)} eligible case(s)"
        )

    return selected


def _cases_from_bundle(bundle: Mapping[str, Any]) -> list[PilotCase]:
    category = str(bundle.get("category") or "").strip()
    owasp_id = bundle.get("owasp_id")
    cases: list[PilotCase] = []
    for template in bundle.get("templates", []) or []:
        template_id = str(template.get("id") or "").strip()
        if not template_id:
            continue
        for payload_index, payload in enumerate(template.get("payloads", []) or []):
            text = str(payload.get("text") or "")
            if not text.strip():
                continue
            cases.append(
                PilotCase(
                    case_id=f"{template_id}:{payload_index}",
                    category=category,
                    owasp_id=str(owasp_id) if owasp_id else None,
                    template_id=template_id,
                    template_name=template.get("name"),
                    payload_index=payload_index,
                    payload_text=text,
                    payload_language=payload.get("language"),
                    payload_variant=payload.get("variant"),
                )
            )
    return cases
```

- [ ] **Step 4: Run selector tests and verify GREEN**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit selector**

```powershell
git add backend/app/services/pilot_runner.py backend/tests/test_pilot_runner_selector.py
git commit -m "feat(pilot): add deterministic pilot case selector"
```

---

### Task 2: Dry-run Artifact Generation

**Files:**
- Modify: `backend/app/services/pilot_runner.py`
- Create: `backend/tests/test_pilot_runner_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

Create `backend/tests/test_pilot_runner_artifacts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pilot_runner import prepare_pilot_run
from app.services.quartet_generator import load_suite

pytestmark = pytest.mark.anyio


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def test_dry_run_writes_config_suite_and_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "run_001"

    result = await prepare_pilot_run(
        output_dir=output_dir,
        case_count=30,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=True,
    )

    assert result.scan_task_id is None
    assert result.selected_case_count == 30
    assert result.planned_variant_count == 120
    assert (output_dir / "config.json").exists()
    assert (output_dir / "suite.json").exists()
    assert (output_dir / "summary.json").exists()

    suite = load_suite(output_dir / "suite.json")
    assert suite.manifest.content_hash == result.suite_hash
    assert suite.manifest.case_count == 30

    config = _read_json(output_dir / "config.json")
    assert config["run_id"] == "run_001"
    assert config["dry_run"] is True
    assert config["selected_case_count"] == 30
    assert config["planned_variant_count"] == 120
    assert config["suite_hash"] == result.suite_hash

    summary = _read_json(output_dir / "summary.json")
    assert summary["planned_variant_count"] == summary["selected_case_count"] * 4
    assert summary["scan_task_id"] is None
    assert "Stage 1.4" in summary["next_step"]


async def test_dry_run_does_not_open_database(tmp_path: Path) -> None:
    def forbidden_session_factory():
        raise AssertionError("dry-run must not open the database")

    result = await prepare_pilot_run(
        output_dir=tmp_path / "dry_run_no_db",
        case_count=6,
        model="gpt-4o-mini",
        target_type="openai_compatible",
        seed=20260504,
        suite_version="v0.1",
        dry_run=True,
        session_factory=forbidden_session_factory,
    )

    assert result.selected_case_count == 6
    assert result.planned_variant_count == 24
```

- [ ] **Step 2: Run artifact tests and verify RED**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_artifacts.py -q
```

Expected: FAIL with import error for `prepare_pilot_run`.

- [ ] **Step 3: Implement dry-run artifact generation**

Extend `backend/app/services/pilot_runner.py` with these imports near the top:

```python
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.quartet_generator import dump_suite, generate_quartet, load_suite
```

Add these types and functions below `PilotCase`:

```python
SessionFactory = Callable[[], AsyncSession]
SUPPORTED_PREPARE_TARGET_TYPES: tuple[str, ...] = (
    "openai_compatible",
    "claude",
    "builtin_vulnerable",
)


@dataclass(frozen=True)
class PilotRunResult:
    run_id: str
    output_dir: Path
    config_path: Path
    suite_path: Path
    summary_path: Path
    suite_hash: str
    selected_case_count: int
    planned_variant_count: int
    dry_run: bool
    scan_task_id: str | None
```

Add this function near the bottom of the file:

```python
async def prepare_pilot_run(
    *,
    output_dir: Path,
    case_count: int = DEFAULT_CASE_COUNT,
    model: str = DEFAULT_MODEL,
    target_type: str = "openai_compatible",
    seed: int = DEFAULT_PILOT_SEED,
    suite_version: str = DEFAULT_SUITE_VERSION,
    run_id: str | None = None,
    dry_run: bool = True,
    templates_dir: Path | None = None,
    session_factory: SessionFactory | None = None,
) -> PilotRunResult:
    target_type = _validate_target_type(target_type)
    output_dir = Path(output_dir)
    run_id = (run_id or output_dir.name).strip()
    if not run_id:
        raise ValueError("run_id must be non-empty")

    bundles = load_attack_template_bundles(templates_dir)
    selected_cases = select_pilot_cases(bundles, case_count=case_count, seed=seed)
    quartet_cases = [
        generate_quartet(
            case_id=case.case_id,
            category=case.category,
            attack_payload=case.payload_text,
            owasp_id=case.owasp_id,
            template_id=case.template_id,
            template_name=case.template_name,
            payload_language=case.payload_language,
            payload_variant=case.payload_variant,
        )
        for case in selected_cases
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    suite_path = output_dir / "suite.json"
    config_path = output_dir / "config.json"
    summary_path = output_dir / "summary.json"

    manifest = dump_suite(
        quartet_cases,
        out_path=suite_path,
        suite_version=suite_version,
        description=f"Pilot run {run_id}",
    )
    verified_suite = load_suite(suite_path)
    if verified_suite.manifest.content_hash != manifest.content_hash:
        raise ValueError("suite hash verification failed after dump")

    planned_variant_count = len(quartet_cases) * 4
    selected_categories = list(dict.fromkeys(case.category for case in selected_cases))
    scan_task_id: str | None = None

    config = _build_config_payload(
        run_id=run_id,
        suite_version=suite_version,
        seed=seed,
        requested_case_count=case_count,
        selected_case_count=len(selected_cases),
        planned_variant_count=planned_variant_count,
        model=model,
        target_type=target_type,
        selected_categories=selected_categories,
        suite_path=suite_path,
        suite_hash=manifest.content_hash,
        dry_run=dry_run,
        scan_task_id=scan_task_id,
    )
    summary = _build_summary_payload(
        run_id=run_id,
        selected_case_count=len(selected_cases),
        planned_variant_count=planned_variant_count,
        suite_hash=manifest.content_hash,
        output_dir=output_dir,
        config_path=config_path,
        suite_path=suite_path,
        summary_path=summary_path,
        dry_run=dry_run,
        scan_task_id=scan_task_id,
    )

    _write_json(config_path, config)
    _write_json(summary_path, summary)

    return PilotRunResult(
        run_id=run_id,
        output_dir=output_dir,
        config_path=config_path,
        suite_path=suite_path,
        summary_path=summary_path,
        suite_hash=manifest.content_hash,
        selected_case_count=len(selected_cases),
        planned_variant_count=planned_variant_count,
        dry_run=dry_run,
        scan_task_id=scan_task_id,
    )
```

Add helpers:

```python
def _validate_target_type(target_type: str) -> str:
    normalized = str(target_type or "").strip()
    if normalized not in SUPPORTED_PREPARE_TARGET_TYPES:
        raise ValueError(
            f"target_type {normalized!r} is not supported by Stage 1.3 Pilot preparation"
        )
    return normalized


def _build_config_payload(
    *,
    run_id: str,
    suite_version: str,
    seed: int,
    requested_case_count: int,
    selected_case_count: int,
    planned_variant_count: int,
    model: str,
    target_type: str,
    selected_categories: list[str],
    suite_path: Path,
    suite_hash: str,
    dry_run: bool,
    scan_task_id: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "suite_version": suite_version,
        "seed": seed,
        "requested_case_count": requested_case_count,
        "selected_case_count": selected_case_count,
        "planned_variant_count": planned_variant_count,
        "model": model,
        "target_type": target_type,
        "category_quotas": {category: 5 for category in PREFERRED_PILOT_CATEGORIES},
        "selected_categories": selected_categories,
        "suite_path": str(suite_path),
        "suite_hash": suite_hash,
        "dry_run": dry_run,
        "scan_task_id": scan_task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_summary_payload(
    *,
    run_id: str,
    selected_case_count: int,
    planned_variant_count: int,
    suite_hash: str,
    output_dir: Path,
    config_path: Path,
    suite_path: Path,
    summary_path: Path,
    dry_run: bool,
    scan_task_id: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "selected_case_count": selected_case_count,
        "planned_variant_count": planned_variant_count,
        "suite_hash": suite_hash,
        "output_dir": str(output_dir),
        "config_path": str(config_path),
        "suite_path": str(suite_path),
        "summary_path": str(summary_path),
        "dry_run": dry_run,
        "scan_task_id": scan_task_id,
        "next_step": "Stage 1.4: execute the prepared scan with real provider configuration.",
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run artifact tests and verify GREEN**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_artifacts.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run selector + artifact tests together**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py backend\tests\test_pilot_runner_artifacts.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit artifacts**

```powershell
git add backend/app/services/pilot_runner.py backend/tests/test_pilot_runner_artifacts.py
git commit -m "feat(pilot): write reproducible pilot dry-run artifacts"
```

---

### Task 3: Pending ScanTask Preparation

**Files:**
- Modify: `backend/app/services/pilot_runner.py`
- Create: `backend/tests/test_pilot_runner_scantask.py`

- [ ] **Step 1: Write failing ScanTask tests**

Create `backend/tests/test_pilot_runner_scantask.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.database import async_session, init_db
from app.models import ScanTask
from app.services.pilot_runner import prepare_pilot_run

pytestmark = pytest.mark.anyio


async def test_prepare_mode_creates_pending_scan_task(tmp_path: Path) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_run",
        case_count=6,
        model="gpt-4o-mini",
        target_type="builtin_vulnerable",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    assert result.scan_task_id is not None

    async with async_session() as db:
        task = (
            await db.execute(select(ScanTask).where(ScanTask.id == result.scan_task_id))
        ).scalar_one()

    assert task.status == "pending"
    assert task.name == "Pilot v0.1 prepared_run"
    assert task.target_type == "builtin_vulnerable"
    assert task.target_url == "builtin"
    assert task.attack_categories == [
        "prompt_injection",
        "system_prompt_extraction",
        "jailbreak",
        "information_disclosure",
        "indirect_injection",
        "excessive_agency",
    ]
    assert task.started_at is None
    assert task.completed_at is None
    assert task.advanced_config["quartet_mode"] == "full"
    assert task.advanced_config["pilot_run_id"] == "prepared_run"
    assert task.advanced_config["pilot_suite_hash"] == result.suite_hash
    assert task.advanced_config["pilot_case_count"] == 6
    assert task.advanced_config["pilot_variant_count"] == 24
    assert task.advanced_config["pilot_seed"] == 20260504
    assert task.advanced_config["pilot_model"] == "gpt-4o-mini"


async def test_prepare_mode_updates_artifacts_with_scan_task_id(tmp_path: Path) -> None:
    await init_db()

    result = await prepare_pilot_run(
        output_dir=tmp_path / "prepared_artifacts",
        case_count=6,
        model="gpt-4o-mini",
        target_type="builtin_vulnerable",
        seed=20260504,
        suite_version="v0.1",
        dry_run=False,
    )

    config = result.config_path.read_text(encoding="utf-8")
    summary = result.summary_path.read_text(encoding="utf-8")
    assert result.scan_task_id is not None
    assert result.scan_task_id in config
    assert result.scan_task_id in summary


async def test_prepare_rejects_custom_and_adapter_targets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not supported"):
        await prepare_pilot_run(
            output_dir=tmp_path / "custom",
            target_type="custom",
            dry_run=True,
        )

    with pytest.raises(ValueError, match="not supported"):
        await prepare_pilot_run(
            output_dir=tmp_path / "adapter",
            target_type="adapter",
            dry_run=True,
        )
```

- [ ] **Step 2: Run ScanTask tests and verify RED**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_scantask.py -q
```

Expected: FAIL because `prepare_pilot_run(..., dry_run=False)` does not create a task yet.

- [ ] **Step 3: Implement pending ScanTask creation**

Add these imports to `backend/app/services/pilot_runner.py`:

```python
from app.database import async_session as default_session_factory
from app.models import ScanTask
```

In `prepare_pilot_run`, replace the `scan_task_id: str | None = None` block with:

```python
    scan_task_id: str | None = None
    if not dry_run:
        scan_task_id = await _create_pending_scan_task(
            run_id=run_id,
            suite_version=suite_version,
            target_type=target_type,
            model=model,
            selected_categories=selected_categories,
            suite_path=suite_path,
            suite_hash=manifest.content_hash,
            selected_case_count=len(selected_cases),
            planned_variant_count=planned_variant_count,
            seed=seed,
            session_factory=session_factory,
        )
```

Keep the existing config/summary construction after this block so `scan_task_id` is written into both files.

Add helper functions:

```python
async def _create_pending_scan_task(
    *,
    run_id: str,
    suite_version: str,
    target_type: str,
    model: str,
    selected_categories: list[str],
    suite_path: Path,
    suite_hash: str,
    selected_case_count: int,
    planned_variant_count: int,
    seed: int,
    session_factory: SessionFactory | None,
) -> str:
    factory = session_factory or default_session_factory
    target_config = _target_config_for_prepare(target_type, model)
    task = ScanTask(
        name=f"Pilot {suite_version} {run_id}",
        status="pending",
        target_url="builtin" if target_type == "builtin_vulnerable" else "pilot-prepared",
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
    async with factory() as db:
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id


def _target_config_for_prepare(target_type: str, model: str) -> dict[str, Any] | None:
    if target_type == "builtin_vulnerable":
        return {"vulnerable_level": 2}
    return {"model": model}
```

- [ ] **Step 4: Run ScanTask tests and verify GREEN**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_scantask.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Run all pilot service tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py backend\tests\test_pilot_runner_artifacts.py backend\tests\test_pilot_runner_scantask.py -q
```

Expected: `9 passed`.

- [ ] **Step 6: Commit ScanTask preparation**

```powershell
git add backend/app/services/pilot_runner.py backend/tests/test_pilot_runner_scantask.py
git commit -m "feat(pilot): prepare pending scan task for pilot runs"
```

---

### Task 4: CLI Wrapper

**Files:**
- Create: `backend/app/scripts/run_pilot.py`
- Create: `backend/tests/test_run_pilot_cli.py`

- [ ] **Step 1: Write failing CLI test**

Create `backend/tests/test_run_pilot_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.scripts import run_pilot


def test_cli_dry_run_writes_artifacts_and_prints_summary(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "cli_run"

    run_pilot.main([
        "--cases",
        "6",
        "--model",
        "gpt-4o-mini",
        "--target-type",
        "openai_compatible",
        "--output-dir",
        str(output_dir),
        "--seed",
        "20260504",
        "--dry-run",
    ])

    captured = capsys.readouterr().out
    assert "run_id=cli_run" in captured
    assert "selected_cases=6" in captured
    assert "planned_variants=24" in captured
    assert "scan_task_id=None" in captured
    assert (output_dir / "config.json").exists()
    assert (output_dir / "suite.json").exists()
    assert (output_dir / "summary.json").exists()
```

- [ ] **Step 2: Run CLI test and verify RED**

Run:

```powershell
python -m pytest backend\tests\test_run_pilot_cli.py -q
```

Expected: FAIL with import error for `app.scripts.run_pilot`.

- [ ] **Step 3: Implement CLI wrapper**

Create `backend/app/scripts/run_pilot.py`:

```python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from collections.abc import Sequence

from app.database import init_db
from app.services.pilot_runner import (
    DEFAULT_CASE_COUNT,
    DEFAULT_MODEL,
    DEFAULT_PILOT_SEED,
    DEFAULT_SUITE_VERSION,
    PilotRunResult,
    prepare_pilot_run,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a reproducible Stage 1 pilot run.")
    parser.add_argument("--cases", type=int, default=DEFAULT_CASE_COUNT)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--target-type", type=str, default="openai_compatible")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_PILOT_SEED)
    parser.add_argument("--suite-version", type=str, default=DEFAULT_SUITE_VERSION)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> PilotRunResult:
    if not args.dry_run:
        await init_db()
    return await prepare_pilot_run(
        output_dir=args.output_dir,
        case_count=args.cases,
        model=args.model,
        target_type=args.target_type,
        seed=args.seed,
        suite_version=args.suite_version,
        run_id=args.run_id,
        dry_run=args.dry_run,
    )


def _format_summary(result: PilotRunResult) -> str:
    return "\n".join(
        [
            f"run_id={result.run_id}",
            f"selected_cases={result.selected_case_count}",
            f"planned_variants={result.planned_variant_count}",
            f"suite_hash={result.suite_hash}",
            f"output_dir={result.output_dir}",
            f"scan_task_id={result.scan_task_id}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = asyncio.run(_run(args))
    print(_format_summary(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI test and verify GREEN**

Run:

```powershell
python -m pytest backend\tests\test_run_pilot_cli.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Run all Stage 1.3 tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py backend\tests\test_pilot_runner_artifacts.py backend\tests\test_pilot_runner_scantask.py backend\tests\test_run_pilot_cli.py -q
```

Expected: `10 passed`.

- [ ] **Step 6: Commit CLI**

```powershell
git add backend/app/scripts/run_pilot.py backend/tests/test_run_pilot_cli.py
git commit -m "feat(pilot): add Stage 1.3 pilot runner CLI"
```

---

### Task 5: Final Verification and Stage 1.3 Commit Hygiene

**Files:**
- Verify: all files changed in Tasks 1-4

- [ ] **Step 1: Run compile verification**

Run:

```powershell
python -m compileall -q backend\app
```

Expected: exit code `0` and no output.

- [ ] **Step 2: Run Stage 1.3 focused tests**

Run:

```powershell
python -m pytest backend\tests\test_pilot_runner_selector.py backend\tests\test_pilot_runner_artifacts.py backend\tests\test_pilot_runner_scantask.py backend\tests\test_run_pilot_cli.py -q
```

Expected: `10 passed`.

- [ ] **Step 3: Run full backend regression**

Run:

```powershell
python -m pytest backend\tests\ -q
```

Expected: all backend tests pass. The current baseline before 1.3 is `159 passed, 2 warnings`; the exact count will increase after adding pilot tests.

- [ ] **Step 4: Run a manual dry-run CLI smoke test**

Run with working directory `backend`:

```powershell
python -m app.scripts.run_pilot --cases 30 --model gpt-4o-mini --target-type openai_compatible --output-dir ..\data\pilot\v0.1\run_001 --seed 20260504 --dry-run
```

Expected output includes:

```text
run_id=run_001
selected_cases=30
planned_variants=120
scan_task_id=None
```

Expected files:

```text
data/pilot/v0.1/run_001/config.json
data/pilot/v0.1/run_001/suite.json
data/pilot/v0.1/run_001/summary.json
```

- [ ] **Step 5: Run diff whitespace check**

Run:

```powershell
git --no-pager diff --check -- backend/app/services/pilot_runner.py backend/app/scripts/run_pilot.py backend/tests/test_pilot_runner_selector.py backend/tests/test_pilot_runner_artifacts.py backend/tests/test_pilot_runner_scantask.py backend/tests/test_run_pilot_cli.py
```

Expected: exit code `0`.

- [ ] **Step 6: Run publication safety scan**

Run:

```powershell
$paths = @(
  'backend/app/services/pilot_runner.py',
  'backend/app/scripts/run_pilot.py',
  'backend/tests/test_pilot_runner_selector.py',
  'backend/tests/test_pilot_runner_artifacts.py',
  'backend/tests/test_pilot_runner_scantask.py',
  'backend/tests/test_run_pilot_cli.py'
)
$secretPattern = "sk-[a-zA-Z0-9]{30,}|Bearer\s+[a-zA-Z0-9]{30,}"
$canaryPrefix = "CANARY" + "-"
$hits = git --no-pager diff -- $paths | Select-String -Pattern "$secretPattern|$canaryPrefix"
if ($hits) { Write-Host "PUB-SAFETY FAIL"; $hits | Out-String } else { Write-Host "PUB-SAFETY OK" }
```

Expected: `PUB-SAFETY OK`.

- [ ] **Step 7: Confirm only Stage 1.3 files are staged**

Run:

```powershell
git status --short
git --no-pager diff --cached --stat
```

Expected staged files only:

```text
backend/app/services/pilot_runner.py
backend/app/scripts/run_pilot.py
backend/tests/test_pilot_runner_selector.py
backend/tests/test_pilot_runner_artifacts.py
backend/tests/test_pilot_runner_scantask.py
backend/tests/test_run_pilot_cli.py
```

Do not stage unrelated `.cursor` or `.gitignore` local changes.

- [ ] **Step 8: Final Stage 1.3 commit if previous tasks were squashed or left uncommitted**

If Tasks 1-4 were already committed individually, skip this step. Otherwise run:

```powershell
git add backend/app/services/pilot_runner.py backend/app/scripts/run_pilot.py backend/tests/test_pilot_runner_selector.py backend/tests/test_pilot_runner_artifacts.py backend/tests/test_pilot_runner_scantask.py backend/tests/test_run_pilot_cli.py
git commit -m "feat(pilot): add Stage 1.3 pilot runner preparation"
```

---

## Self-Review

- Spec coverage:
  - CLI options are covered in Task 4.
  - Deterministic 30-case selection is covered in Task 1.
  - Quartet suite generation and `suite.json` integrity are covered in Task 2.
  - `config.json` and `summary.json` are covered in Task 2.
  - Pending `ScanTask` creation without `run_scan` is covered in Task 3.
  - Full verification and publication-safety are covered in Task 5.
- Placeholder scan:
  - No placeholder markers or vague deferred implementation steps remain.
- Type consistency:
  - `PilotCase`, `PilotRunResult`, `prepare_pilot_run`, and `select_pilot_cases` are introduced before later tasks use them.
  - `scan_task_id`, `suite_hash`, `selected_case_count`, and `planned_variant_count` names match across service, artifacts, and tests.
