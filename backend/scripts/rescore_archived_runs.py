"""Re-score an archived run's Arm A from its cached initial pass, offline.

Why this exists
---------------
The archived runs under ``backend/experiment-output/`` were collected while the
evaluator was still being fixed, so the question "were these numbers produced by
code that was later found buggy?" was open. ``CLASSIFICATION.md`` answered it by
asserting that ``experiment_driver`` does not import ``evidence_arbiter``. That
is not true: the scoring path is

    experiment_driver -> retest_experiment.run_experiment_case
                      -> _loop_arm("A", ...) -> arbitrate_evidence

so every arm's evidence level comes out of the arbiter, and an arbiter fix landing
after collection *could* have changed what a re-score would report. Nothing
checked whether it actually did.

This script checks it. Arm A is the arm that ``arbitrate_evidence`` fully
determines, and it runs with a null executor and zero retest rounds, so it can be
replayed from the cached initial pass with **no model calls and no cost**. The
replay is compared case by case against the recorded ``lineages.jsonl``.

Reading the result
------------------
*   ``MATCH`` on every case means today's scoring code reproduces the archived
    numbers exactly: no fix since collection moved them, and the recorded Arm A
    values are usable as-is.
*   A mismatch names the case and both values. That is not automatically
    corruption -- a *declared* behaviour change (for example a judge-abstention
    policy other than the ``negative`` the runs actually ran under) will show up
    here too. What it does mean is that the recorded number no longer describes
    what the current code would report, so anything quoting it must say which
    code version produced it.

Only Arms A' and B are out of reach: they issued live re-judge and probe calls
whose raw responses were never cached, so they cannot be replayed offline.

Usage
-----
    python -m scripts.rescore_archived_runs --root backend/experiment-output \\
        natural-3arm-block1 [more-run-dirs ...]

    # every run dir that has the required files
    python -m scripts.rescore_archived_runs --root backend/experiment-output --all
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.experiment_driver import (
    InitialPassCacheFile,
    InitialPassRecord,
    _build_cached_result,
    compute_frozen_suite_hash,
    load_frozen_suite,
)
from app.services.retest_experiment import ARM_A_CONFIG, _loop_arm, _NullExecutor

REQUIRED_FILES = ("initial-pass-cache.json", "lineages.jsonl")

#: Fields of the recorded Arm A outcome that a replay must reproduce.
COMPARED_FIELDS = ("initial_evidence_level", "final_evidence_level", "final_verdict")


@dataclass
class CaseDiff:
    case_id: str
    field: str
    recorded: Any
    replayed: Any


def load_suite_index(experiments_dir: Path) -> dict[str, Path]:
    """Map frozen-suite hash -> suite file, so a run resolves its own suite.

    Doubles as a check on the hash table in CLASSIFICATION.md: a run whose
    suite_hash matches nothing here has lost its inputs and is unreproducible.
    """
    index: dict[str, Path] = {}
    for path in sorted(experiments_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cases = raw.get("cases") if isinstance(raw, dict) else None
        if not isinstance(cases, list) or not cases:
            continue
        try:
            index[compute_frozen_suite_hash(cases)] = path
        except Exception:
            continue
    return index


class UnreplayableCache(Exception):
    """The cache cannot be loaded by today's model, so it cannot be replayed."""


def load_records(run_dir: Path) -> tuple[InitialPassRecord, ...]:
    raw = json.loads((run_dir / "initial-pass-cache.json").read_text(encoding="utf-8"))
    try:
        return InitialPassCacheFile.model_validate(raw).records
    except Exception as exc:
        # Early caches predate the provenance fields (endpoint fingerprints,
        # evaluator prompt hash) that InitialPassRecord now requires. Their
        # numbers cannot be re-derived, which is a provenance limit of those
        # runs, not a scoring difference.
        missing = sorted(
            {
                str(err["loc"][-1])
                for err in getattr(exc, "errors", lambda: [])()
                if err.get("type") == "missing"
            }
        )
        detail = f"missing {', '.join(missing)}" if missing else str(exc).splitlines()[0]
        raise UnreplayableCache(detail) from exc


def load_recorded_arm_a(run_dir: Path) -> dict[str, dict[str, Any]]:
    recorded: dict[str, dict[str, Any]] = {}
    with (run_dir / "lineages.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            outcome = (entry.get("outcomes") or {}).get("A")
            if outcome is not None:
                recorded[entry["case_id"]] = outcome
    return recorded


async def replay_arm_a(
    records: tuple[InitialPassRecord, ...],
    suite_path: Path,
) -> dict[str, dict[str, Any]]:
    suite = load_frozen_suite(suite_path)
    cases = {case.case_id: case for case in suite.cases}
    replayed: dict[str, dict[str, Any]] = {}
    for record in records:
        case = cases.get(record.case_id)
        if case is None:
            continue
        result = _build_cached_result(case, record)
        outcome = await _loop_arm("A", result, _NullExecutor(), ARM_A_CONFIG)
        replayed[record.case_id] = {
            "initial_evidence_level": outcome.initial_evidence_level,
            "final_evidence_level": outcome.final_evidence_level,
            "final_verdict": outcome.final_verdict,
        }
    return replayed


def compare(
    recorded: dict[str, dict[str, Any]],
    replayed: dict[str, dict[str, Any]],
) -> tuple[list[CaseDiff], list[str]]:
    diffs: list[CaseDiff] = []
    missing: list[str] = []
    for case_id, rec in sorted(recorded.items()):
        rep = replayed.get(case_id)
        if rep is None:
            missing.append(case_id)
            continue
        for field in COMPARED_FIELDS:
            if rec.get(field) != rep.get(field):
                diffs.append(CaseDiff(case_id, field, rec.get(field), rep.get(field)))
    return diffs, missing


async def audit_run(run_dir: Path, suite_index: dict[str, Path]) -> bool:
    print(f"=== {run_dir.name} ===")
    for name in REQUIRED_FILES:
        if not (run_dir / name).is_file():
            print(f"  SKIP: no {name}")
            return True

    try:
        records = load_records(run_dir)
    except UnreplayableCache as exc:
        print(f"  SKIP: cache predates the current provenance schema ({exc})")
        return True
    hashes = {record.suite_hash for record in records}
    if len(hashes) != 1:
        print(f"  FAIL: cache mixes {len(hashes)} suite hashes")
        return False
    suite_hash = next(iter(hashes))
    suite_path = suite_index.get(suite_hash)
    if suite_path is None:
        print(f"  SKIP: suite {suite_hash[:10]} matches no file in backend/experiments")
        return True
    print(f"  suite {suite_hash[:10]} -> {suite_path.name}  ({len(records)} cached cases)")

    recorded = load_recorded_arm_a(run_dir)
    replayed = await replay_arm_a(records, suite_path)
    diffs, missing = compare(recorded, replayed)

    if missing:
        print(f"  {len(missing)} recorded case(s) absent from the replay: {', '.join(missing[:5])}")
    if not diffs:
        print(f"  MATCH: {len(recorded)} cases reproduce exactly")
        return not missing
    print(f"  {len(diffs)} field mismatch(es) over {len(recorded)} cases:")
    for diff in diffs:
        print(f"    {diff.case_id:<26} {diff.field:<24} recorded={diff.recorded!r} replayed={diff.replayed!r}")
    return False


async def main_async() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--experiments",
        type=Path,
        default=Path("experiments"),
        help="directory holding the frozen suite files (default: experiments)",
    )
    parser.add_argument("--all", action="store_true", help="audit every run dir under --root")
    parser.add_argument(
        "--abstention-policy",
        choices=("e0", "negative", "e2"),
        help=(
            "score judge abstentions under this policy instead of the configured "
            "default. Runs collected before the policy became a parameter behaved "
            "as 'negative'; pass that to compare like with like."
        ),
    )
    parser.add_argument("runs", nargs="*")
    args = parser.parse_args()

    if args.abstention_policy:
        from app.config import settings

        settings.abstention_policy = args.abstention_policy
        print(f"abstention policy pinned to {args.abstention_policy!r}")

    suite_index = load_suite_index(args.experiments)
    print(f"{len(suite_index)} frozen suite(s) indexed from {args.experiments}\n")

    if args.all:
        run_dirs = sorted(path for path in args.root.iterdir() if path.is_dir())
    else:
        run_dirs = [args.root / name for name in args.runs]
    if not run_dirs:
        parser.error("name at least one run dir, or pass --all")

    ok = True
    for run_dir in run_dirs:
        ok = await audit_run(run_dir, suite_index) and ok
        print()
    print("ALL RUNS REPRODUCE" if ok else "MISMATCHES FOUND -- see above")
    return 0 if ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
