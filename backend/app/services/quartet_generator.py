from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.quartet import (
    BenchmarkSuite,
    QuartetPrompts,
    QuartetVariantSet,
    SuiteManifest,
)
from app.services.control_variants import (
    CONTROL_VARIANT_VERSION,
    build_control_variant_prompts,
)


def generate_quartet(
    *,
    case_id: str,
    category: str,
    attack_payload: str,
    owasp_id: str | None = None,
    template_id: str | None = None,
    template_name: str | None = None,
    payload_language: str | None = None,
    payload_variant: str | None = None,
) -> QuartetPrompts:
    if not attack_payload or not attack_payload.strip():
        raise ValueError("attack_payload must be non-empty")

    template_like: dict = {"category": category}
    control_prompts = build_control_variant_prompts(template_like, attack_payload)
    by_variant = {entry["variant"]: entry["prompt"] for entry in control_prompts}

    return QuartetPrompts(
        case_id=case_id,
        category=category,
        owasp_id=owasp_id,
        template_id=template_id,
        template_name=template_name,
        payload_language=payload_language,
        payload_variant=payload_variant,
        protocol_version=CONTROL_VARIANT_VERSION,
        variants=QuartetVariantSet(
            attack=attack_payload,
            clean=by_variant["clean"],
            quoted_attack=by_variant["quoted_attack"],
            benign_distractor=by_variant["benign_distractor"],
        ),
    )


def _canonical_cases_json(cases: list[dict]) -> str:
    sorted_cases = sorted(cases, key=lambda c: c.get("case_id", ""))
    return json.dumps(sorted_cases, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _content_hash(cases: list[dict]) -> str:
    return hashlib.sha256(_canonical_cases_json(cases).encode("utf-8")).hexdigest()


def dump_suite(
    cases: Iterable[QuartetPrompts],
    *,
    out_path: Path,
    suite_version: str,
    description: str | None = None,
) -> SuiteManifest:
    cases_list = list(cases)
    cases_dicts = [c.model_dump(mode="json") for c in cases_list]
    content_hash = _content_hash(cases_dicts)

    manifest = SuiteManifest(
        suite_version=suite_version,
        generated_at=datetime.now(timezone.utc),
        case_count=len(cases_list),
        content_hash=content_hash,
        protocol_version=CONTROL_VARIANT_VERSION,
        description=description,
    )

    payload = {
        "manifest": manifest.model_dump(mode="json"),
        "cases": cases_dicts,
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=out_path.parent,
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    tmp_path.replace(out_path)

    return manifest


def load_suite(path: Path) -> BenchmarkSuite:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    manifest_data = raw["manifest"]
    cases_data = raw["cases"]

    actual_hash = _content_hash(cases_data)
    expected_hash = manifest_data["content_hash"]

    if actual_hash != expected_hash:
        raise ValueError(
            f"Suite content hash mismatch (integrity check failed): "
            f"expected {expected_hash!r}, got {actual_hash!r}"
        )

    cases = [QuartetPrompts.model_validate(c) for c in cases_data]
    manifest = SuiteManifest.model_validate(manifest_data)

    return BenchmarkSuite(manifest=manifest, cases=cases)
