"""Regression tests for the ``backfill_posture_rollups`` maintenance CLI.

These tests pin down three invariants:

1. A scan whose ``vulnerabilities_found`` / ``overall_score`` was
   written under the old 口径 (e.g. counting ``manual_review_needed``
   cases as vulnerabilities) gets rewritten to the current verdict-
   driven values.
2. Running the backfill a second time is a no-op — the diff list still
   enumerates every scan, but no row reports ``changed == True``. This
   guarantees operators can rerun the script without worrying about
   double-writes.
3. ``--dry-run`` computes the same diff but leaves the DB untouched,
   and ``--scan-id`` narrows the sweep to a single task.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AttackResult, ScanTask
from app.scripts.backfill_posture_rollups import backfill


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass  # Windows: SQLite file still held by aiosqlite


class BackfillPostureRollupsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.addCleanup(lambda p=tmp.name: _safe_unlink(p))
        self.db_path = tmp.name
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///" + self.db_path.replace("\\", "/"),
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _insert_scan(
        self,
        *,
        name: str,
        stale_vuln: int,
        stale_score: float | None,
        results: list[tuple[str, bool, float, str]],
        status: str = "completed",
    ) -> str:
        """Create a scan with AttackResults and deliberately stale rollups.

        ``results`` is a list of ``(verdict_status, attack_successful,
        risk_score, risk_level)`` tuples so the test can pick any
        combination of verdict classes.
        """
        async with self.session_factory() as session:
            task = ScanTask(
                name=name,
                target_url="mock://target",
                target_type="generic",
                status=status,
                total_attacks=len(results),
                completed_attacks=len(results),
                vulnerabilities_found=stale_vuln,
                overall_score=stale_score,
            )
            session.add(task)
            await session.flush()
            for idx, (verdict_status, attack_successful, risk_score, risk_level) in enumerate(
                results
            ):
                session.add(
                    AttackResult(
                        scan_task_id=task.id,
                        template_id=f"T{idx}",
                        category="prompt_injection",
                        technique="unit",
                        attack_name=f"Attack {idx}",
                        payload_text="payload",
                        target_response="response",
                        attack_successful=attack_successful,
                        confidence=0.9 if attack_successful else 0.1,
                        risk_level=risk_level,
                        risk_score=risk_score,
                        analysis_raw={"verdict_status": verdict_status},
                    )
                )
            await session.commit()
            return task.id

    async def test_drifted_scan_gets_aligned(self):
        """A scan with a stale headline number must be rewritten."""
        # 5 cases: 1 confirmed + 2 needs_review (one True, one False to
        # cover the verdict/attack_successful disagreement path) + 2 passed.
        # Under the new 口径: confirmed_findings = 1, not 3 or 999.
        scan_id = await self._insert_scan(
            name="drifted",
            stale_vuln=999,
            stale_score=0.0,
            results=[
                ("rule_verified", True, 8.0, "high"),
                ("manual_review_needed", True, 0.0, "none"),
                ("manual_review_needed", False, 0.0, "none"),
                ("passed", False, 0.0, "none"),
                ("passed", False, 0.0, "none"),
            ],
        )

        diffs = await backfill(session_factory=self.session_factory)
        self.assertEqual(len(diffs), 1)
        diff = diffs[0]
        self.assertEqual(diff.scan_id, scan_id)
        self.assertTrue(diff.changed)
        self.assertEqual(diff.old_vuln, 999)
        self.assertEqual(diff.new_vuln, 1)

        # Confirm the write reached the DB.
        async with self.session_factory() as session:
            stored = await session.get(ScanTask, scan_id)
            self.assertEqual(stored.vulnerabilities_found, 1)

    async def test_second_run_is_a_noop(self):
        """Idempotency guard: rerunning must not flag any change."""
        await self._insert_scan(
            name="drifted",
            stale_vuln=999,
            stale_score=0.0,
            results=[
                ("rule_verified", True, 8.0, "high"),
                ("manual_review_needed", True, 0.0, "none"),
                ("passed", False, 0.0, "none"),
            ],
        )

        first = await backfill(session_factory=self.session_factory)
        self.assertTrue(first[0].changed)

        second = await backfill(session_factory=self.session_factory)
        self.assertEqual(len(second), 1)
        self.assertFalse(second[0].changed)
        # new_vuln on the second pass matches the first pass's output.
        self.assertEqual(second[0].new_vuln, first[0].new_vuln)
        self.assertEqual(second[0].old_vuln, first[0].new_vuln)

    async def test_dry_run_does_not_write(self):
        """``--dry-run`` surfaces the diff without touching the DB."""
        scan_id = await self._insert_scan(
            name="dry-run",
            stale_vuln=42,
            stale_score=99.9,
            results=[("rule_verified", True, 8.0, "high")],
        )

        diffs = await backfill(session_factory=self.session_factory, dry_run=True)
        self.assertEqual(len(diffs), 1)
        self.assertTrue(diffs[0].changed)
        self.assertEqual(diffs[0].new_vuln, 1)  # diff says "would write 1"

        # DB still shows the stale value.
        async with self.session_factory() as session:
            stored = await session.get(ScanTask, scan_id)
            self.assertEqual(stored.vulnerabilities_found, 42)

    async def test_scan_id_filter_only_touches_one_scan(self):
        """With ``--scan-id``, other scans must not be re-rolled."""
        id_target = await self._insert_scan(
            name="target",
            stale_vuln=100,
            stale_score=10.0,
            results=[("rule_verified", True, 8.0, "high")],
        )
        id_untouched = await self._insert_scan(
            name="untouched",
            stale_vuln=100,
            stale_score=10.0,
            results=[("manual_review_needed", True, 0.0, "none")],
        )

        diffs = await backfill(
            session_factory=self.session_factory, scan_id=id_target
        )
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].scan_id, id_target)
        self.assertEqual(diffs[0].new_vuln, 1)

        # Untouched scan keeps its stale rollup number.
        async with self.session_factory() as session:
            stored = await session.get(ScanTask, id_untouched)
            self.assertEqual(stored.vulnerabilities_found, 100)

    async def test_pending_and_running_scans_are_skipped(self):
        """Scans without stable results must not be touched."""
        async with self.session_factory() as session:
            pending = ScanTask(
                name="pending",
                target_url="mock://x",
                status="pending",
                vulnerabilities_found=7,
            )
            running = ScanTask(
                name="running",
                target_url="mock://x",
                status="running",
                vulnerabilities_found=3,
            )
            session.add_all([pending, running])
            await session.commit()

        diffs = await backfill(session_factory=self.session_factory)
        self.assertEqual(diffs, [])

        # Headline numbers on the in-progress scans are left alone even
        # though they'd otherwise look "stale" — the backfill only rolls
        # up scans that have finalized their result set.
        async with self.session_factory() as session:
            still_pending = await session.get(ScanTask, pending.id)
            still_running = await session.get(ScanTask, running.id)
            self.assertEqual(still_pending.vulnerabilities_found, 7)
            self.assertEqual(still_running.vulnerabilities_found, 3)


if __name__ == "__main__":
    unittest.main()
