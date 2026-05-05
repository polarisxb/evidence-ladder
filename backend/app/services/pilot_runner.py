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
