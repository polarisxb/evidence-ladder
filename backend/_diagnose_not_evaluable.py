"""One-shot read-only diagnostic: print the response_evaluation breakdown
for the most recent scan (or a specific scan by id / name substring).

Usage:
    python _diagnose_not_evaluable.py                 # latest scan
    python _diagnose_not_evaluable.py <scan_id>       # by full id
    python _diagnose_not_evaluable.py --name TAP      # by name substring

Safe to delete after diagnosis.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "app.db"

def _pick_scan(conn: sqlite3.Connection, arg: str | None) -> sqlite3.Row | None:
    if arg and arg != "--name":
        row = conn.execute(
            "SELECT * FROM scan_tasks WHERE id = ? OR name = ?", (arg, arg)
        ).fetchone()
        if row:
            return row
    if sys.argv[1:2] == ["--name"] and len(sys.argv) >= 3:
        pattern = f"%{sys.argv[2]}%"
        return conn.execute(
            "SELECT * FROM scan_tasks WHERE name LIKE ? ORDER BY created_at DESC LIMIT 1",
            (pattern,),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM scan_tasks ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def _extract_resp_eval(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        blob = json.loads(raw)
    except Exception:
        return None
    if not isinstance(blob, dict):
        return None
    direct = blob.get("response_evaluation")
    if isinstance(direct, dict):
        return direct
    return None


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    scan = _pick_scan(conn, arg)
    if scan is None:
        print("No scan_tasks matched.")
        return 1

    print("=" * 80)
    print(f"SCAN  id={scan['id']}")
    print(f"      name={scan['name']!r}")
    print(f"      status={scan['status']}")
    print(f"      target_type={scan['target_type']}  target_url={scan['target_url']}")
    print(f"      target_health={scan['target_health']}  "
          f"health_probe_passed={scan['health_probe_passed']}  "
          f"invalid_ratio={scan['invalid_response_ratio']}")
    print(f"      completed={scan['completed_attacks']}/{scan['total_attacks']}"
          f"   vulns={scan['vulnerabilities_found']}")
    print(f"      recent_health_signature={scan['recent_health_signature']!r}")
    print(f"      health_failure_reason={scan['health_failure_reason']!r}")
    print("=" * 80)

    cases = conn.execute(
        """
        SELECT id, template_id, technique, attack_name, case_status, case_final_outcome,
               verdict_status, verdict_reason, business_verification_status, summary_json
          FROM attack_cases
         WHERE scan_task_id = ?
         ORDER BY created_at ASC
        """,
        (scan["id"],),
    ).fetchall()

    print(f"\nTotal cases: {len(cases)}\n")

    # Aggregate distributions across all variants of all cases.
    reason_counter: Counter[str] = Counter()
    origin_counter: Counter[str] = Counter()
    http_counter: Counter[str] = Counter()
    signature_counter: Counter[str] = Counter()
    verdict_counter: Counter[str] = Counter()

    per_case_summary: list[dict] = []

    for case in cases:
        variants = conn.execute(
            """
            SELECT id, variant_type, position, is_primary, response_status,
                   response_text, response_error, analysis_raw
              FROM attack_case_variants
             WHERE attack_case_id = ?
             ORDER BY position ASC
            """,
            (case["id"],),
        ).fetchall()

        primary = next(
            (v for v in variants if v["is_primary"] or v["variant_type"] == "attack"),
            variants[0] if variants else None,
        )
        resp_eval = _extract_resp_eval(primary["analysis_raw"]) if primary else None

        verdict_counter[case["verdict_status"] or "(none)"] += 1
        if resp_eval:
            reason_counter[resp_eval.get("invalid_reason") or "(none)"] += 1
            origin_counter[resp_eval.get("response_origin") or "(none)"] += 1
            http_counter[str(resp_eval.get("http_status")) if resp_eval.get("http_status") is not None else "(none)"] += 1
            if resp_eval.get("matched_signature"):
                signature_counter[resp_eval["matched_signature"]] += 1

        per_case_summary.append({
            "case": case,
            "primary": primary,
            "resp_eval": resp_eval,
        })

    def _print_counter(title: str, ctr: Counter[str]) -> None:
        print(f"-- {title} --")
        if not ctr:
            print("  (empty)")
        else:
            for k, v in ctr.most_common():
                print(f"  {v:4d}  {k}")
        print()

    _print_counter("verdict_status distribution", verdict_counter)
    _print_counter("response_evaluation.invalid_reason distribution", reason_counter)
    _print_counter("response_evaluation.response_origin distribution", origin_counter)
    _print_counter("response_evaluation.http_status distribution", http_counter)
    _print_counter("response_evaluation.matched_signature distribution", signature_counter)

    # Print per-case detail (first 30 to keep output bounded)
    MAX_DETAIL = 30
    print("-" * 80)
    print(f"Per-case detail (first {min(MAX_DETAIL, len(per_case_summary))}):")
    print("-" * 80)
    for entry in per_case_summary[:MAX_DETAIL]:
        c = entry["case"]
        p = entry["primary"]
        e = entry["resp_eval"] or {}
        resp_text = (p["response_text"] if p else None) or ""
        resp_err = (p["response_error"] if p else None) or ""
        snippet_src = resp_err or resp_text
        snippet = (snippet_src[:160] + "…") if len(snippet_src) > 160 else snippet_src
        snippet = snippet.replace("\n", "  ")
        print(
            f"\n[{c['template_id']}] {c['attack_name']}\n"
            f"   verdict={c['verdict_status']!r}  final_outcome={c['case_final_outcome']!r}"
            f"   primary_resp_status={p['response_status'] if p else None!r}\n"
            f"   resp_origin={e.get('response_origin')!r}"
            f"   invalid_reason={e.get('invalid_reason')!r}"
            f"   http={e.get('http_status')!r}"
            f"   transport_ok={e.get('transport_ok')!r}\n"
            f"   matched_signature={e.get('matched_signature')!r}"
            f"   content_type={e.get('content_type')!r}\n"
            f"   snippet={snippet!r}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
