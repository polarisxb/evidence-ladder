from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from app.database import async_session, init_db
from app.models import ScanTask
from app.services.llm_scheduler import init_scheduler
from app.services.scan_runner import run_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a prepared Stage 1 pilot ScanTask.")
    parser.add_argument("--scan-task-id", required=True)
    return parser


async def _load_scan_task(scan_task_id: str) -> ScanTask | None:
    async with async_session() as db:
        return await db.get(ScanTask, scan_task_id)


async def _run(args: argparse.Namespace) -> ScanTask:
    await init_db()
    # The scheduler singletons are normally created by the FastAPI lifespan; this
    # standalone entrypoint must initialise them too, otherwise every LLM call
    # fails with "Scheduler not initialized".
    await init_scheduler()
    await run_scan(args.scan_task_id, {})
    task = await _load_scan_task(args.scan_task_id)
    if task is None:
        raise SystemExit(f"scan_task_id={args.scan_task_id} was not found after execution")
    return task


def _format_summary(task: ScanTask) -> str:
    return "\n".join(
        [
            f"scan_task_id={task.id}",
            f"status={task.status}",
            f"completed_attacks={task.completed_attacks}",
            f"total_attacks={task.total_attacks}",
            f"vulnerabilities_found={task.vulnerabilities_found}",
            f"overall_score={task.overall_score}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    task = asyncio.run(_run(args))
    print(_format_summary(task))


if __name__ == "__main__":
    main()
