from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.experiment_driver import (
    GroundTruthArtifact,
    _find_forbidden_evidence_paths,
    _resolve_case_ground_truth,
    compute_model_matrix_hash,
    load_frozen_suite,
    load_model_matrix,
)
from app.services.response_screening import TargetResponseEnvelope

_EVIDENCE_ORDER = {None: -1, "E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5}
_REQUIRED_OUTPUTS = (
    "initial-pass-cache.json",
    "lineages.jsonl",
    "results.csv",
    "results.json",
    "run-manifest.json",
)
_MODEL_CALL_METADATA_KEYS = {
    "requested_model",
    "provider_type",
    "requested_at",
    "returned_model",
    "system_fingerprint",
    "response_id",
    "request_id",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_cached_ground_truth(case: Any, record: dict[str, Any]) -> bool:
    raw_artifact = record.get("ground_truth_artifact")
    artifact = (
        GroundTruthArtifact.model_validate(raw_artifact)
        if isinstance(raw_artifact, dict)
        else None
    )
    return _resolve_case_ground_truth(
        case,
        TargetResponseEnvelope.model_validate(record.get("target_response", {})),
        artifact,
    )


def _audit_call_metadata(
    metadata: Any,
    *,
    label: str,
    requested_model: str,
    errors: list[str],
) -> None:
    if not isinstance(metadata, dict):
        errors.append(f"{label}: missing provider call metadata")
        return
    missing_keys = sorted(_MODEL_CALL_METADATA_KEYS - set(metadata))
    if missing_keys:
        errors.append(f"{label}: missing metadata fields: {', '.join(missing_keys)}")
    if metadata.get("requested_model") != requested_model:
        errors.append(f"{label}: requested model does not match the model matrix")
    total_tokens = metadata.get("total_tokens")
    if total_tokens is not None and (
        not isinstance(total_tokens, int) or total_tokens < 0
    ):
        errors.append(f"{label}: invalid total_tokens metadata")


def audit_output(
    *,
    suite_path: Path,
    models_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    suite = load_frozen_suite(suite_path)
    matrix = load_model_matrix(models_path)

    for filename in _REQUIRED_OUTPUTS:
        if not (out_dir / filename).is_file():
            errors.append(f"missing required output: {filename}")
    if errors:
        return {
            "status": "failed",
            "publication_ready": False,
            "errors": errors,
            "warnings": warnings,
        }

    cache = _load_json(out_dir / "initial-pass-cache.json")
    results = _load_json(out_dir / "results.json")
    manifest = _load_json(out_dir / "run-manifest.json")
    lineages = [
        json.loads(line)
        for line in (out_dir / "lineages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    targets = matrix.target_models
    expected_records = len(suite.cases) * len(targets)
    cached_records = cache.get("records", [])
    if len(cached_records) != expected_records:
        errors.append(
            f"initial cache has {len(cached_records)} records; expected {expected_records}"
        )
    if len(lineages) != expected_records:
        errors.append(f"lineage export has {len(lineages)} records; expected {expected_records}")

    suite_case_ids = {case.case_id for case in suite.cases}
    expected_case_counts = {
        case_id: len(targets) for case_id in suite_case_ids
    }
    cache_case_counts = {
        case_id: sum(record.get("case_id") == case_id for record in cached_records)
        for case_id in suite_case_ids
    }
    lineage_case_counts = {
        case_id: sum(record.get("case_id") == case_id for record in lineages)
        for case_id in suite_case_ids
    }
    if cache_case_counts != expected_case_counts:
        errors.append("initial cache case coverage does not match the frozen suite")
    if lineage_case_counts != expected_case_counts:
        errors.append("lineage case coverage does not match the frozen suite")

    cases_by_id = {case.case_id: case for case in suite.cases}
    targets_by_id = {model.model_id: model for model in targets}
    lineages_by_key = {
        (record.get("model_id"), record.get("case_id")): record
        for record in lineages
    }
    for record in cached_records:
        case_id = record.get("case_id")
        if record.get("suite_hash") != suite.content_hash:
            errors.append(f"cache suite hash mismatch for {case_id}")
        forbidden = _find_forbidden_evidence_paths(record.get("raw_evaluation", {}))
        if forbidden:
            errors.append(
                f"forbidden evidence in initial evaluation for {record.get('case_id')}: "
                + ", ".join(sorted(forbidden))
            )
        if not record.get("target_response", {}).get("transport_ok", False):
            errors.append(f"non-transport-ok cached response for {case_id}")
        target_model = targets_by_id.get(record.get("model_id"))
        target_response = record.get("target_response", {})
        if target_model is not None and target_model.provider_id != "builtin":
            _audit_call_metadata(
                target_response.get("transport_meta", {}).get("model_call"),
                label=f"{case_id}/initial-target",
                requested_model=target_model.pinned_version,
                errors=errors,
            )
        if matrix.judge_model.provider_id != "builtin":
            _audit_call_metadata(
                record.get("judge_call_metadata"),
                label=f"{case_id}/initial-judge",
                requested_model=matrix.judge_model.pinned_version,
                errors=errors,
            )
        case = cases_by_id.get(case_id)
        lineage = lineages_by_key.get((record.get("model_id"), case_id))
        if case is not None and lineage is not None:
            resolved_ground_truth = _resolve_cached_ground_truth(case, record)
            if lineage.get("ground_truth") != resolved_ground_truth:
                errors.append(
                    f"{case_id}: exported ground truth does not match the frozen oracle"
                )

    for record in lineages:
        case_id = record.get("case_id")
        outcomes = record.get("outcomes", {})
        if set(outcomes) != {"A", "A_prime", "B"}:
            errors.append(f"{case_id}: missing or unexpected experiment arms")
            continue
        forbidden = _find_forbidden_evidence_paths(outcomes)
        if forbidden:
            errors.append(
                f"{case_id}: forbidden scoring evidence entered arm outcomes: "
                + ", ".join(sorted(forbidden))
            )
        for arm, outcome in outcomes.items():
            level = outcome.get("final_evidence_level")
            if arm in {"A", "A_prime"} and _EVIDENCE_ORDER.get(level, -1) > 2:
                errors.append(f"{case_id}/{arm}: evidence exceeded the E2 cap")
            target_queries = int(outcome.get("target_retest_queries") or 0)
            judge_queries = int(outcome.get("judge_queries") or 0)
            probe_steps = int(outcome.get("probe_steps") or 0)
            extra_queries = int(outcome.get("extra_queries") or 0)
            if extra_queries != target_queries + judge_queries + probe_steps:
                errors.append(
                    f"{case_id}/{arm}: total query count does not equal its breakdown"
                )
        arm_a = outcomes["A"]
        if any(
            int(arm_a.get(field) or 0)
            for field in (
                "extra_queries",
                "target_retest_queries",
                "judge_queries",
                "probe_steps",
            )
        ):
            errors.append(f"{case_id}/A: judge-only arm spent an extra query")
        arm_ap = outcomes["A_prime"]
        if (
            int(arm_ap.get("target_retest_queries") or 0) != 0
            or int(arm_ap.get("probe_steps") or 0) != 0
            or int(arm_ap.get("judge_queries") or 0) != 1
        ):
            errors.append(f"{case_id}/A_prime: invalid re-judge query breakdown")
        if matrix.verifier_model.provider_id != "builtin":
            _audit_call_metadata(
                arm_ap.get("judge_call_metadata"),
                label=f"{case_id}/A_prime",
                requested_model=matrix.verifier_model.pinned_version,
                errors=errors,
            )
        arm_b = outcomes["B"]
        if arm_b.get("lineage") is None:
            errors.append(f"{case_id}/B: missing retest lineage")
        target_model = targets_by_id.get(record.get("model_id"))
        if target_model is not None and target_model.provider_id != "builtin":
            target_queries = int(arm_b.get("target_retest_queries") or 0)
            judge_queries = int(arm_b.get("judge_queries") or 0)
            metadata_entries = [
                metadata
                for round_payload in arm_b.get("lineage", {}).get("rounds", [])
                if isinstance(round_payload, dict)
                for metadata in round_payload.get("model_call_metadata", [])
                if isinstance(metadata, dict)
            ]
            target_metadata = [
                metadata
                for metadata in metadata_entries
                if metadata.get("call_role") in {None, "target"}
            ]
            judge_metadata = [
                metadata
                for metadata in metadata_entries
                if metadata.get("call_role") == "judge"
            ]
            if len(target_metadata) != target_queries:
                errors.append(
                    f"{case_id}/B: target retest metadata count does not match calls"
                )
            if len(judge_metadata) != judge_queries:
                errors.append(
                    f"{case_id}/B: retest judge metadata count does not match calls"
                )
            for metadata in target_metadata:
                _audit_call_metadata(
                    metadata,
                    label=f"{case_id}/B target",
                    requested_model=target_model.pinned_version,
                    errors=errors,
                )
            for metadata in judge_metadata:
                _audit_call_metadata(
                    metadata,
                    label=f"{case_id}/B judge",
                    requested_model=matrix.judge_model.pinned_version,
                    errors=errors,
                )

    if manifest.get("suite_hash") != suite.content_hash:
        errors.append("manifest suite hash does not match the frozen suite")
    actual_matrix_hash = compute_model_matrix_hash(
        matrix.models,
        allow_rolling_aliases=matrix.allow_rolling_aliases,
    )
    if manifest.get("model_matrix_hash") != actual_matrix_hash:
        errors.append("manifest model matrix hash does not match the configured matrix")
    if matrix.content_hash is None:
        warnings.append("model matrix does not declare a frozen content hash")
    if manifest.get("model_matrix") != matrix.model_dump(mode="json"):
        errors.append("manifest model matrix does not match the configured matrix")
    if manifest.get("config", {}).get("human_gold_provided") is not False:
        warnings.append("human-gold status is not explicitly false")
    if not manifest.get("call_usage"):
        errors.append("manifest is missing call-usage provenance")
    else:
        call_usage = manifest["call_usage"]
        if (
            call_usage.get("common_initial_target", {}).get("calls")
            != expected_records
        ):
            errors.append("manifest initial-target call count is inconsistent")
        if (
            call_usage.get("common_initial_judge", {}).get("calls")
            != expected_records
        ):
            errors.append("manifest initial-judge call count is inconsistent")
        expected_incremental_calls = {
            arm: sum(
                int(record.get("outcomes", {}).get(arm, {}).get("extra_queries") or 0)
                for record in lineages
            )
            for arm in ("A", "A_prime", "B")
        }
        for arm, expected_calls in expected_incremental_calls.items():
            observed_calls = (
                call_usage.get("arm_incremental", {})
                .get(arm, {})
                .get("calls")
            )
            if observed_calls != expected_calls:
                errors.append(f"manifest {arm} call count is inconsistent")
    if manifest.get("collection_block_id") in {None, "", "unspecified"}:
        warnings.append("collection block is not explicitly identified")

    for scope, table in (
        ("pooled", results.get("pooled", {})),
        *[
            (f"per_model/{model_id}", model_table)
            for model_id, model_table in results.get("per_model", {}).items()
        ],
    ):
        for arm, metrics in table.items():
            kappa = metrics.get("judge_vs_human_kappa", {})
            if manifest.get("config", {}).get("human_gold_provided") is False and not (
                kappa.get("pending") is True and kappa.get("value") == "PENDING"
            ):
                errors.append(f"{scope}/{arm}: human kappa was fabricated")

    identities = manifest.get("model_identities", [])
    unresolved = [
        identity.get("model_id")
        for identity in identities
        if identity.get("provider_id") != "builtin"
        and not identity.get("actual_model_revision")
    ]
    if unresolved:
        warnings.append(
            "unresolved actual model revisions: " + ", ".join(str(item) for item in unresolved)
        )
    if (
        matrix.judge_model.provider_id == matrix.verifier_model.provider_id
        and matrix.judge_model.pinned_version == matrix.verifier_model.pinned_version
    ):
        warnings.append("judge and verifier use the same provider/model")
    if len(suite.cases) < 30:
        warnings.append(f"small suite: {len(suite.cases)} cases")
    warnings.append(
        "percentile bootstrap intervals are degenerate for all-zero/all-one cells"
    )

    checksums = {
        filename: _sha256(out_dir / filename)
        for filename in _REQUIRED_OUTPUTS
    }
    publication_ready = not errors and not warnings
    return {
        "status": "passed" if not errors else "failed",
        "publication_ready": publication_ready,
        "suite_hash": suite.content_hash,
        "expected_records": expected_records,
        "cache_records": len(cached_records),
        "lineage_records": len(lineages),
        "errors": errors,
        "warnings": warnings,
        "checksums": checksums,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_output(
        suite_path=args.suite,
        models_path=args.models,
        out_dir=args.out,
    )
    report_path = args.out / "integrity-audit.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
