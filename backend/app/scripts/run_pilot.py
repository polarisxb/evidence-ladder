from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

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
