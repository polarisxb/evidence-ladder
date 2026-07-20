from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BlockSpec:
    matrix: str
    output: str
    collection_block_id: str
    execution_seed: int
    bootstrap_seed: int


BLOCKS = (
    BlockSpec(
        matrix="formal_pilot_j55_v54_models.json",
        output="formal-pilot-j55-v54-block1",
        collection_block_id="formal-j55-v54-block1",
        execution_seed=1101,
        bootstrap_seed=2101,
    ),
    BlockSpec(
        matrix="formal_pilot_j55_v54_models.json",
        output="formal-pilot-j55-v54-block2",
        collection_block_id="formal-j55-v54-block2",
        execution_seed=1102,
        bootstrap_seed=2102,
    ),
    BlockSpec(
        matrix="formal_pilot_j55_v54_models.json",
        output="formal-pilot-j55-v54-block3",
        collection_block_id="formal-j55-v54-block3",
        execution_seed=1103,
        bootstrap_seed=2103,
    ),
    BlockSpec(
        matrix="formal_pilot_j54_v55_models.json",
        output="formal-pilot-j54-v55-block1",
        collection_block_id="formal-j54-v55-block1",
        execution_seed=1201,
        bootstrap_seed=2201,
    ),
    BlockSpec(
        matrix="formal_pilot_j54_v55_models.json",
        output="formal-pilot-j54-v55-block2",
        collection_block_id="formal-j54-v55-block2",
        execution_seed=1202,
        bootstrap_seed=2202,
    ),
    BlockSpec(
        matrix="formal_pilot_j54_v55_models.json",
        output="formal-pilot-j54-v55-block3",
        collection_block_id="formal-j54-v55-block3",
        execution_seed=1203,
        bootstrap_seed=2203,
    ),
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_passed(output: Path) -> bool:
    audit_path = output / "integrity-audit.json"
    if not audit_path.exists():
        return False
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return audit.get("status") == "passed" and not audit.get("errors")


def _write_status(path: Path, statuses: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "updated_at": _timestamp(),
                "blocks": statuses,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    backend = Path(__file__).resolve().parents[1]
    suite = backend / "experiments" / "formal_pilot_canary_suite.json"
    status_path = backend / "experiment-output" / "formal-pilot-runner-status.json"
    statuses: list[dict[str, object]] = []

    for block in BLOCKS:
        output = backend / "experiment-output" / block.output
        output.mkdir(parents=True, exist_ok=True)
        status: dict[str, object] = {
            **asdict(block),
            "started_at": _timestamp(),
            "status": "running",
        }
        statuses.append(status)
        _write_status(status_path, statuses)

        if _audit_passed(output):
            status["status"] = "skipped_already_passed"
            status["completed_at"] = _timestamp()
            _write_status(status_path, statuses)
            continue

        run_command = [
            sys.executable,
            "-m",
            "scripts.run_experiment",
            "--suite",
            str(suite),
            "--models",
            str(backend / "experiments" / block.matrix),
            "--out",
            str(output),
            "--collection-block-id",
            block.collection_block_id,
            "--execution-seed",
            str(block.execution_seed),
            "--bootstrap-seed",
            str(block.bootstrap_seed),
            "--bootstrap-resamples",
            "5000",
        ]
        if (output / "initial-pass-cache.json").exists():
            run_command.append("--resume")

        with (output / "runner-experiment.log").open(
            "a",
            encoding="utf-8",
        ) as log:
            log.write(f"\n[{_timestamp()}] starting experiment\n")
            log.flush()
            run_result = subprocess.run(
                run_command,
                cwd=backend,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if run_result.returncode != 0:
            status["status"] = "failed_experiment"
            status["returncode"] = run_result.returncode
            status["completed_at"] = _timestamp()
            (output / "INVALID_DO_NOT_USE").write_text(
                "Experiment command failed. Retain artifacts for diagnosis only.\n",
                encoding="utf-8",
            )
            _write_status(status_path, statuses)
            raise SystemExit(run_result.returncode)

        audit_command = [
            sys.executable,
            "-m",
            "scripts.audit_experiment_output",
            "--suite",
            str(suite),
            "--models",
            str(backend / "experiments" / block.matrix),
            "--out",
            str(output),
        ]
        with (output / "runner-audit.log").open(
            "a",
            encoding="utf-8",
        ) as log:
            log.write(f"\n[{_timestamp()}] starting audit\n")
            log.flush()
            audit_result = subprocess.run(
                audit_command,
                cwd=backend,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if audit_result.returncode != 0 or not _audit_passed(output):
            status["status"] = "failed_audit"
            status["returncode"] = audit_result.returncode
            status["completed_at"] = _timestamp()
            (output / "INVALID_DO_NOT_USE").write_text(
                "Integrity audit failed. Retain artifacts for diagnosis only.\n",
                encoding="utf-8",
            )
            _write_status(status_path, statuses)
            raise SystemExit(audit_result.returncode or 1)

        status["status"] = "passed"
        status["completed_at"] = _timestamp()
        _write_status(status_path, statuses)


if __name__ == "__main__":
    main()
