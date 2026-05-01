"""Analyse Arbiter shadow output recorded under ``analysis_raw.arbiter_shadow``.

Run after a scan finishes with ``verdict_arbiter_shadow_mode=True`` (or
``verdict_arbiter_enabled=True``) to compare what the new Arbiter would
have said versus the legacy ``classify_verdict``. The script is read-only:
it never mutates DB rows.

Typical usage::

    # show diff over all scans
    python -m app.scripts.analyze_arbiter_shadow_diff

    # focus on one scan
    python -m app.scripts.analyze_arbiter_shadow_diff --scan-id 61df9f13

    # show 5 sample case ids per (legacy_status -> arbiter_status) bucket
    python -m app.scripts.analyze_arbiter_shadow_diff --samples 5

Per-bucket samples make it easy to grep the corresponding case_ids in
the UI / DB and decide whether the Arbiter call is the better one.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = Path("data/app.db")


@dataclass
class CaseDiff:
    case_id: str
    scan_id: str
    legacy_status: str
    arbiter_status: str
    arbiter_rule: str | None
    needs_review_category: str | None
    error: str | None


def _decode_analysis_raw(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8", errors="replace")
        except Exception:
            return {}
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _iter_case_diffs(
    conn: sqlite3.Connection, scan_id_prefix: str | None
) -> Iterable[CaseDiff]:
    sql = "SELECT id, scan_task_id, analysis_raw FROM attack_results"
    params: tuple = ()
    if scan_id_prefix:
        sql += " WHERE scan_task_id LIKE ?"
        params = (f"{scan_id_prefix}%",)

    for row in conn.execute(sql, params):
        raw = _decode_analysis_raw(row["analysis_raw"])
        shadow = raw.get("arbiter_shadow")
        if not isinstance(shadow, dict):
            # Either flag is off or this case predates the shadow rollout.
            continue

        legacy_status = str(raw.get("verdict_status") or "<NULL>")
        if shadow.get("error"):
            yield CaseDiff(
                case_id=row["id"],
                scan_id=row["scan_task_id"],
                legacy_status=legacy_status,
                arbiter_status="<error>",
                arbiter_rule=None,
                needs_review_category=None,
                error=str(shadow.get("error")),
            )
            continue

        arbiter_status = str(shadow.get("status") or "<NULL>")
        # When enabled mode is on, the legacy verdict is preserved
        # under arbiter_shadow.legacy_verdict.status — prefer that for
        # an apples-to-apples comparison.
        legacy_under_shadow = (shadow.get("legacy_verdict") or {}).get("status")
        if isinstance(legacy_under_shadow, str) and legacy_under_shadow:
            legacy_status = legacy_under_shadow

        yield CaseDiff(
            case_id=row["id"],
            scan_id=row["scan_task_id"],
            legacy_status=legacy_status,
            arbiter_status=arbiter_status,
            arbiter_rule=shadow.get("rule_hit"),
            needs_review_category=shadow.get("needs_review_category"),
            error=None,
        )


def _print_distribution(diffs: list[CaseDiff], samples_per_bucket: int) -> None:
    if not diffs:
        print("No arbiter_shadow records found. Did you enable "
              "settings.verdict_arbiter_shadow_mode and re-scan?")
        return

    print(f"Total cases analysed: {len(diffs)}")

    legacy_counter: Counter[str] = Counter(d.legacy_status for d in diffs)
    arbiter_counter: Counter[str] = Counter(d.arbiter_status for d in diffs)

    print("\nLegacy verdict distribution:")
    for status, n in legacy_counter.most_common():
        print(f"  {n:5d}  {status}")

    print("\nArbiter verdict distribution:")
    for status, n in arbiter_counter.most_common():
        print(f"  {n:5d}  {status}")

    rule_counter: Counter[str] = Counter(
        (d.arbiter_rule or "<none>") for d in diffs if d.error is None
    )
    if rule_counter:
        print("\nArbiter rule distribution (excl. errors):")
        for rule, n in rule_counter.most_common():
            print(f"  {n:5d}  {rule}")

    diff_buckets: dict[tuple[str, str], list[CaseDiff]] = defaultdict(list)
    for d in diffs:
        if d.legacy_status != d.arbiter_status:
            diff_buckets[(d.legacy_status, d.arbiter_status)].append(d)

    if not diff_buckets:
        print("\nNo disagreements: legacy and arbiter agree on every case.")
        return

    total_diff = sum(len(v) for v in diff_buckets.values())
    print(f"\nDisagreements: {total_diff} of {len(diffs)} "
          f"({total_diff / len(diffs):.0%})")
    print("Top disagreement buckets:")

    sorted_buckets = sorted(
        diff_buckets.items(), key=lambda item: -len(item[1])
    )
    for (legacy_s, arbiter_s), bucket in sorted_buckets:
        print(f"\n  {len(bucket):4d}  legacy={legacy_s} -> arbiter={arbiter_s}")
        for sample in bucket[:samples_per_bucket]:
            review_cat = (
                f", review={sample.needs_review_category}"
                if sample.needs_review_category
                else ""
            )
            rule = sample.arbiter_rule or "<none>"
            print(
                f"      case_id={sample.case_id[:8]} "
                f"scan_id={sample.scan_id[:8]} "
                f"rule={rule}{review_cat}"
            )

    error_count = sum(1 for d in diffs if d.error)
    if error_count:
        print(f"\nArbiter errors: {error_count}")
        # Show 5 unique error messages.
        error_msgs: Counter[str] = Counter(d.error for d in diffs if d.error)
        for msg, n in error_msgs.most_common(5):
            print(f"  {n:4d}  {msg}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--scan-id",
        default=None,
        help="scan_task_id prefix to filter (e.g. '61df9f13')",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="number of sample case_ids to print per disagreement bucket",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        diffs = list(_iter_case_diffs(conn, args.scan_id))

    _print_distribution(diffs, args.samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
