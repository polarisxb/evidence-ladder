"""Cross-check the UI 'running now' list with DB state.

Given the three names the UI shows as in-flight, figure out:
  - Are these templates actually started on the backend?
  - Have any of their case attempts been persisted already?
  - How many LLM calls (httpx POST to target/judge) happened since each
    attack_started, to tell if the case is making progress or truly stuck.
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path

NAMES = ["Authority Impersonation", "Context Delimiter Injection", "Role Hijacking - DAN"]
LOG = Path("uvicorn.live.log")

c = sqlite3.connect("./data/app.db")
c.row_factory = sqlite3.Row
scan = c.execute(
    "SELECT id, status, completed_attacks, total_attacks FROM scan_tasks "
    "ORDER BY created_at DESC LIMIT 1"
).fetchone()
print(f"Scan {scan['id'][:8]}  status={scan['status']}  {scan['completed_attacks']}/{scan['total_attacks']}")

# Has each name ever been persisted as an attack_result? (If yes: already done)
for name in NAMES:
    row = c.execute(
        "SELECT COUNT(*) AS n, MAX(created_at) AS last FROM attack_results "
        "WHERE scan_task_id = ? AND attack_name = ?",
        (scan["id"], name),
    ).fetchone()
    print(f"  \"{name}\": persisted={row['n']}  last={row['last']}")

# Scan log for the most recent attack_started/attack_completed of these names
# (these come as WebSocket frames logged by uvicorn access only if we print
# them; scan_runner currently only broadcasts, not logs. Fall back to the
# httpx POST rate as a proxy for activity.)
print("\nRecent httpx POSTs in last 200 lines (proxy for LLM traffic):")
text = LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
posts = [l for l in text if "POST http" in l or "POST https" in l]
for l in posts[-12:]:
    m = re.match(r"(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)", l)
    stamp = m.group(1) if m else "?"
    url = re.search(r"POST (\S+)", l)
    print(f"  {stamp}  {url.group(1) if url else l}")

# Any timeouts in the last 200 lines?
timeouts = [l for l in text if "timed out" in l]
print(f"\nTimeouts in last 200 lines: {len(timeouts)}")
for l in timeouts[-6:]:
    print(f"  {l.strip()[:160]}")
