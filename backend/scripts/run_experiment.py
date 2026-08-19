from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from app.services.experiment_driver import describe_dirty_source, execute_experiment_run

#: The frozen protocol (formal-pilot.v1) pre-registers `manual_review` as a
#: reported positive in the primary judge-reporting estimand, which is the `e2`
#: abstention policy -- not the product default `e0`. Pinning it here keeps a paid
#: run from silently deviating from its own pre-registration. Change this only by
#: amending the protocol under a new version.
PROTOCOL_ABSTENTION_POLICY = "e2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a frozen retest experiment across a pinned model matrix."
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("experiment-output"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--collection-block-id", type=str, default="unspecified")
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--execution-seed", type=int, default=0)
    parser.add_argument("--bootstrap-resamples", type=int, default=1000)
    parser.add_argument(
        "--abstention-policy",
        choices=("e0", "negative", "e2"),
        default=PROTOCOL_ABSTENTION_POLICY,
        help=(
            "how a judge abstention scores. Defaults to the value the frozen "
            "protocol pre-registers (e2); overriding it deviates from the "
            "pre-registered estimand and must be reported as such."
        ),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "collect even though there are uncommitted source changes. The run "
            "will not be reproducible from any commit; only use this for throwaway "
            "dry runs."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    dirty = describe_dirty_source(Path.cwd().parent)
    if dirty and not args.allow_dirty:
        raise SystemExit(
            "refusing to collect from a dirty source tree: "
            f"{dirty}\n"
            "The manifest would record a dirty_tree_hash that matches no commit, so "
            "the run could never be re-scored -- commit first, or pass --allow-dirty "
            "for a throwaway dry run."
        )
    if dirty:
        print(f"WARNING: collecting from a dirty tree ({dirty}); run is unreproducible")

    from app.config import settings

    settings.abstention_policy = args.abstention_policy
    print(f"abstention policy: {args.abstention_policy} (protocol pre-registers e2)")

    result = asyncio.run(
        execute_experiment_run(
            suite_path=args.suite,
            models_path=args.models,
            out_dir=args.out,
            resume=args.resume,
            run_id=args.run_id,
            collection_block_id=args.collection_block_id,
            bootstrap_seed=args.bootstrap_seed,
            execution_seed=args.execution_seed,
            bootstrap_resamples=args.bootstrap_resamples,
        )
    )
    print(result.exports.table_json.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
