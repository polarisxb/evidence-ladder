import sqlite3
from datetime import datetime

c = sqlite3.connect("./data/app.db")
c.row_factory = sqlite3.Row

# latest scan
row = c.execute(
    "SELECT id, status, started_at FROM scan_tasks ORDER BY created_at DESC LIMIT 1"
).fetchone()
print(f"Scan {row['id'][:8]}  status={row['status']}  started={row['started_at']}")

results = c.execute(
    "SELECT created_at, attack_name FROM attack_results "
    "WHERE scan_task_id = ? ORDER BY created_at ASC",
    (row["id"],),
).fetchall()
print(f"Persisted results: {len(results)}")
prev = None
for i, r in enumerate(results, 1):
    ts = datetime.fromisoformat(r["created_at"])
    delta = f"{(ts - prev).total_seconds():.1f}s" if prev else "-"
    print(f"  {i:>2}. {r['created_at']}  (+{delta})  {r['attack_name']}")
    prev = ts

# what timestamp is the DB seeing "now"
now = datetime.fromisoformat(c.execute("SELECT datetime('now') as n").fetchone()["n"])
last = datetime.fromisoformat(results[-1]["created_at"]) if results else None
if last:
    idle = (now - last).total_seconds()
    print(f"\nSeconds since last result persisted: {idle:.1f}s")
