from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as default_session_factory
from app.models import ScanTask
from app.services.quartet_generator import dump_suite, generate_quartet, load_suite


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
SessionFactory = Callable[[], AsyncSession]
SUPPORTED_PREPARE_TARGET_TYPES: tuple[str, ...] = (
    "openai_compatible",
    "claude",
    "builtin_vulnerable",
)


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
    async with factory() as db:
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id


def _target_url_for_prepare(target_type: str) -> str:
    if target_type == "builtin_vulnerable":
        return "builtin"
    if target_type == "openai_compatible":
        return "default"
    return "default"


def _target_config_for_prepare(target_type: str, model: str) -> dict[str, Any] | None:
    if target_type == "builtin_vulnerable":
        return {"vulnerable_level": 2}
    return {"model": model}
