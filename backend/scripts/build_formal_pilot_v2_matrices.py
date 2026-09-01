from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.experiment_driver import compute_model_matrix_hash
from scripts.provider_local_ids import apply_local_provider_ids


def _load_roster(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _provider_id(roster: dict[str, Any], slot_name: str) -> str:
    return roster["provider_slots"][slot_name]["provider_id"]


def _target_entry(roster: dict[str, Any], target: dict[str, Any]) -> dict[str, str]:
    return {
        "model_id": target["model_id"],
        "provider_id": _provider_id(roster, target["provider_slot"]),
        "pinned_version": target["pinned_version"],
        "expected_returned_model": target["expected_returned_model"],
        "role": "target",
    }


def _role_entry(
    roster: dict[str, Any],
    *,
    spec: dict[str, str],
    role: str,
) -> dict[str, str]:
    return {
        "model_id": spec["model_id"],
        "provider_id": _provider_id(roster, spec["provider_slot"]),
        "pinned_version": spec["pinned_version"],
        "expected_returned_model": spec["expected_returned_model"],
        "role": role,
    }


def _build_matrix(
    roster: dict[str, Any],
    *,
    target_specs: list[dict[str, Any]],
    judge_key: str,
    verifier_key: str,
) -> dict[str, object]:
    models = [_target_entry(roster, target) for target in target_specs]
    models.append(
        _role_entry(
            roster,
            spec=roster["judges"][judge_key],
            role="judge",
        )
    )
    models.append(
        _role_entry(
            roster,
            spec=roster["verifiers"][verifier_key],
            role="verifier",
        )
    )
    allow_rolling_aliases = False
    return {
        "matrix_version": "retest-model-matrix.v1",
        "content_hash": compute_model_matrix_hash(
            models,
            allow_rolling_aliases=allow_rolling_aliases,
        ),
        "models": models,
        "allow_rolling_aliases": allow_rolling_aliases,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rebuild formal-pilot v2 matrices from the roster.")
    parser.add_argument(
        "--apply-local-ids",
        action="store_true",
        help=(
            "overlay experiments/.provider_ids.local.json onto provider_slots. "
            "Do not commit the resulting hashes unless those UUIDs are meant to be public."
        ),
    )
    args = parser.parse_args(argv)

    roster_path = Path("experiments/model_roster.v2.json")
    roster = _load_roster(roster_path)
    targets_by_slot = {target["slot"]: target for target in roster["targets"]}
    experiments_dir = Path("experiments")
    if args.apply_local_ids:
        applied = apply_local_provider_ids(roster, experiments_dir)
        if applied:
            print(f"applied local provider ids for: {', '.join(applied)}")

    for matrix_spec in roster["matrices"]:
        payload = _build_matrix(
            roster,
            target_specs=list(targets_by_slot.values()),
            judge_key=matrix_spec["judge_key"],
            verifier_key=matrix_spec["verifier_key"],
        )
        output = experiments_dir / matrix_spec["filename"]
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{output}: {payload['content_hash']}")

    gate = roster["paid_gate_matrix"]
    gate_targets = [targets_by_slot[slot] for slot in gate["targets"]]
    gate_payload = _build_matrix(
        roster,
        target_specs=gate_targets,
        judge_key=gate["judge_key"],
        verifier_key=gate["verifier_key"],
    )
    gate_output = experiments_dir / gate["filename"]
    gate_output.write_text(
        json.dumps(gate_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{gate_output}: {gate_payload['content_hash']}")


if __name__ == "__main__":
    main()
