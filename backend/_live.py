import sqlite3
c = sqlite3.connect("./data/app.db")
c.row_factory = sqlite3.Row
rows = c.execute(
    "SELECT id, status, completed_attacks, total_attacks, target_health, "
    "health_failure_reason, started_at, completed_at "
    "FROM scan_tasks ORDER BY created_at DESC LIMIT 2"
).fetchall()
for r in rows:
    print(f"{r['id'][:8]}  status={r['status']:<10}  {r['completed_attacks']}/{r['total_attacks']}  health={r['target_health']}")
    print(f"  started:  {r['started_at']}")
    print(f"  finished: {r['completed_at']}")
    if r['health_failure_reason']:
        print(f"  reason:   {r['health_failure_reason']}")

    # count latest attack_results to see if it's still progressing
    cur = c.execute(
        "SELECT COUNT(*) as n, MAX(created_at) as last FROM attack_results WHERE scan_task_id = ?",
        (r['id'],),
    ).fetchone()
    print(f"  persisted results: {cur['n']}   last at: {cur['last']}")
    print()
