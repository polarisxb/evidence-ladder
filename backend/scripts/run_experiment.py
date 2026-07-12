from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from app.services.experiment_driver import execute_experiment_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a frozen retest experiment across a pinned model matrix."
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("experiment-output"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--bootstrap-resamples", type=int, default=1000)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = asyncio.run(
        execute_experiment_run(
            suite_path=args.suite,
            models_path=args.models,
            out_dir=args.out,
            resume=args.resume,
            run_id=args.run_id,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_resamples=args.bootstrap_resamples,
        )
    )
    print(result.exports.table_json.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
