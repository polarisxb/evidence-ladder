"""One-off maintenance CLI: recompute ``vulnerabilities_found`` and
``overall_score`` for every persisted scan using the current finding
classifier 口径.

Why this exists
---------------
Historically ``vulnerabilities_found`` was written inconsistently across
the three code paths that touch it (``scan_runner``, ``scan_recovery``,
and ``api.reports._refresh_scan_rollups``). Phase 1 unified them on
``finding_classifier.is_confirmed_finding`` — confirmed + suspected —
but old rows stayed stuck at whatever 口径 was active when the scan
finished. This script rolls them forward.

Invariants
----------
- Idempotent: running twice produces the same DB state (the first run
  writes aligned values, the second is a no-op).
- Reuses the exact same function the live review flow calls
  (``_refresh_scan_rollups``), so a scan re-rolled after a manual
  review keeps matching numbers. Any change to the live rollup logic
  is picked up here for free.

Usage
-----
    python -m app.scripts.backfill_posture_rollups             # write all
    python -m app.scripts.backfill_posture_rollups --dry-run   # preview
    python -m app.scripts.backfill_posture_rollups --scan-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.reports import _refresh_scan_rollups
from app.database import async_session as default_session_factory
from app.models import ScanTask


@dataclass
class RollupDiff:
    scan_id: str
    scan_name: str
    status: str
    old_vuln: int
    new_vuln: int
    old_score: float | None
    new_score: float | None

    @property
    def changed(self) -> bool:
        if self.old_vuln != self.new_vuln:
            return True
        # Treat a None → value (or vice versa) as a change even though the
        # raw float equality would miss it. Compare with a tiny epsilon so
        # that incidental 1e-12 drift from recomputing the same inputs in
        # a different order never flags a "change" on a truly aligned row.
        old = self.old_score if self.old_score is not None else float("nan")
        new = self.new_score if self.new_score is not None else float("nan")
        if (self.old_score is None) != (self.new_score is None):
            return True
        if self.old_score is None and self.new_score is None:
            return False
        return abs(old - new) > 0.05  # scores are rounded to 1 decimal


# Statuses we process. "pending" / "running" have no stable results yet.
_TERMINAL_STATUSES: tuple[str, ...] = ("completed", "failed", "cancelled")


SessionFactory = Callable[[], AsyncSession]


async def backfill(
    *,
    dry_run: bool = False,
    scan_id: str | None = None,
    session_factory: SessionFactory | None = None,
) -> list[RollupDiff]:
    """Recompute scan rollups and return a diff per scan.

    Parameters
    ----------
    dry_run:
        If ``True`` the session is rolled back after every scan is
        recomputed, so the diff list shows what *would* change without
        actually writing.
    scan_id:
        If provided, only this scan is processed (useful when
        investigating a single drifted row). The status filter is
        bypassed in that case.
    session_factory:
        Override the default ``async_session`` factory. Primarily used
        by the regression test to run against an in-memory SQLite.
    """
    factory = session_factory or default_session_factory
    async with factory() as session:
        if scan_id:
            stmt = select(ScanTask).where(ScanTask.id == scan_id)
        else:
            stmt = (
                select(ScanTask)
                .where(ScanTask.status.in_(_TERMINAL_STATUSES))
                .order_by(ScanTask.created_at.desc())
            )
        tasks = (await session.execute(stmt)).scalars().all()

        diffs: list[RollupDiff] = []
        for task in tasks:
            old_vuln = task.vulnerabilities_found
            old_score = task.overall_score
            # ``_refresh_scan_rollups`` re-queries the task inside the
            # same session so the SQLAlchemy identity map returns the
            # same instance we're holding here. After the call the
            # in-memory task reflects the new rollup values.
            await _refresh_scan_rollups(session, task.id)
            diffs.append(
                RollupDiff(
                    scan_id=task.id,
                    scan_name=task.name,
                    status=task.status,
                    old_vuln=old_vuln,
                    new_vuln=task.vulnerabilities_found,
                    old_score=old_score,
                    new_score=task.overall_score,
                )
            )

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return diffs


def _format_row(d: RollupDiff) -> str:
    marker = "~" if d.changed else " "
    old_score = f"{d.old_score:.1f}" if d.old_score is not None else "  — "
    new_score = f"{d.new_score:.1f}" if d.new_score is not None else "  — "
    return (
        f"{marker} {d.scan_id[:8]} [{d.status:>9s}] "
        f"vuln {d.old_vuln:>3d} → {d.new_vuln:<3d}  "
        f"score {old_score:>5s} → {new_score:<5s}  "
        f"{d.scan_name}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute vulnerabilities_found / overall_score for all scans "
            "using the current finding classifier 口径."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the DB.",
    )
    parser.add_argument(
        "--scan-id",
        type=str,
        default=None,
        help="Only process this scan id (bypasses the status filter).",
    )
    args = parser.parse_args()

    diffs = asyncio.run(backfill(dry_run=args.dry_run, scan_id=args.scan_id))
    changed = [d for d in diffs if d.changed]

    for d in diffs:
        print(_format_row(d))

    action = "WOULD WRITE" if args.dry_run else "WROTE"
    print()
    print(
        f"{action}: {len(changed)} scan(s) updated, "
        f"{len(diffs) - len(changed)} already aligned"
    )


if __name__ == "__main__":
    main()
