"""Mark zombie scans (status=running but no live scan_runner process) as
failed. Run this once after backend restart kills a running scan mid-flight.

Safe: only touches scans whose started_at is older than 60s AND status is
still 'running' or 'pending', i.e. clearly not about to finalize themselves.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

conn = sqlite3.connect("./data/app.db")
conn.row_factory = sqlite3.Row

# Anything still running but started > 60s ago and not yet completed is a
# zombie (the live run_scan coroutine polls every few seconds, so in
# practice a real scan always updates well inside that window).
cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(" ")

zombies = conn.execute(
    "SELECT id, status, completed_attacks, total_attacks, started_at "
    "FROM scan_tasks "
    "WHERE status IN ('running', 'pending') "
    "AND (started_at IS NULL OR started_at < ?) "
    "AND completed_at IS NULL",
    (cutoff,),
).fetchall()

if not zombies:
    print("No zombie scans found.")
else:
    print(f"Found {len(zombies)} zombie scan(s):")
    for z in zombies:
        print(f"  {z['id'][:8]}  status={z['status']}  "
              f"{z['completed_attacks']}/{z['total_attacks']}  "
              f"started={z['started_at']}")
    print()

    now = datetime.now(timezone.utc).isoformat(" ")
    for z in zombies:
        conn.execute(
            "UPDATE scan_tasks SET status = 'failed', "
            "completed_at = ?, "
            "health_failure_reason = COALESCE(health_failure_reason, ?) "
            "WHERE id = ?",
            (now, "Scan runner crashed or was killed; marked failed on recovery.", z["id"]),
        )
    conn.commit()
    print(f"Marked {len(zombies)} scan(s) as failed.")
