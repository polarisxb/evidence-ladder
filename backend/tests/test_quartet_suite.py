from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.quartet import BenchmarkSuite, QuartetPrompts, SuiteManifest
from app.services.quartet_generator import dump_suite, generate_quartet, load_suite


def _make_case(case_id: str, category: str = "prompt_injection") -> QuartetPrompts:
    return generate_quartet(
        case_id=case_id,
        category=category,
        attack_payload=f"payload-for-{case_id}",
        template_id=case_id.split(":")[0],
        payload_language="en",
        payload_variant="base",
    )


def test_dump_suite_writes_json_with_manifest(tmp_path: Path) -> None:
    cases = [_make_case("PI-001:0"), _make_case("PI-002:0")]
    out = tmp_path / "suite.json"

    manifest = dump_suite(cases, out_path=out, suite_version="v0.1-test")

    assert out.exists()
    assert isinstance(manifest, SuiteManifest)
    assert manifest.case_count == 2
    assert manifest.suite_version == "v0.1-test"

    written = json.loads(out.read_text(encoding="utf-8"))
    assert "manifest" in written
    assert "cases" in written
    assert len(written["cases"]) == 2
    assert written["manifest"]["content_hash"] == manifest.content_hash


def test_content_hash_is_deterministic(tmp_path: Path) -> None:
    cases = [_make_case("PI-001:0"), _make_case("PI-002:0")]

    m1 = dump_suite(cases, out_path=tmp_path / "a.json", suite_version="v0.1")
    m2 = dump_suite(cases, out_path=tmp_path / "b.json", suite_version="v0.1")

    assert m1.content_hash == m2.content_hash


def test_content_hash_changes_with_case_content(tmp_path: Path) -> None:
    cases_a = [_make_case("PI-001:0")]
    cases_b = [
        generate_quartet(
            case_id="PI-001:0",
            category="prompt_injection",
            attack_payload="DIFFERENT payload than _make_case would produce",
            template_id="PI-001",
        )
    ]

    m_a = dump_suite(cases_a, out_path=tmp_path / "a.json", suite_version="v0.1")
    m_b = dump_suite(cases_b, out_path=tmp_path / "b.json", suite_version="v0.1")

    assert m_a.content_hash != m_b.content_hash


def test_content_hash_stable_across_case_ordering(tmp_path: Path) -> None:
    cases_ordered = [_make_case("PI-001:0"), _make_case("PI-002:0"), _make_case("PI-003:0")]
    cases_shuffled = [cases_ordered[2], cases_ordered[0], cases_ordered[1]]

    m1 = dump_suite(cases_ordered, out_path=tmp_path / "ordered.json", suite_version="v0.1")
    m2 = dump_suite(cases_shuffled, out_path=tmp_path / "shuffled.json", suite_version="v0.1")

    assert m1.content_hash == m2.content_hash


def test_round_trip_preserves_all_cases(tmp_path: Path) -> None:
    cases = [
        _make_case("PI-001:0", category="prompt_injection"),
        _make_case("SPE-001:0", category="system_prompt_extraction"),
        _make_case("JB-001:0", category="jailbreak"),
    ]
    out = tmp_path / "suite.json"
    dump_suite(cases, out_path=out, suite_version="v0.1", description="round-trip test")

    loaded = load_suite(out)

    assert isinstance(loaded, BenchmarkSuite)
    assert loaded.manifest.case_count == 3
    assert loaded.manifest.description == "round-trip test"
    loaded_by_id = {c.case_id: c for c in loaded.cases}
    for original in cases:
        reloaded = loaded_by_id[original.case_id]
        assert reloaded == original


def test_load_suite_detects_tampering(tmp_path: Path) -> None:
    cases = [_make_case("PI-001:0"), _make_case("PI-002:0")]
    out = tmp_path / "suite.json"
    dump_suite(cases, out_path=out, suite_version="v0.1")

    raw = json.loads(out.read_text(encoding="utf-8"))
    raw["cases"][0]["variants"]["attack"] = "TAMPERED"
    out.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="hash|integrity"):
        load_suite(out)
