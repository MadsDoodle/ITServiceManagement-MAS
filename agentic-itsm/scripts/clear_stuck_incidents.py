"""
Clear stuck incidents from previous broken workflow runs.
Marks all non-resolved incidents as completed=1 / lifecycle_stage='resolved'
so they stop blocking new injections.

Usage:
  python scripts/clear_stuck_incidents.py           # preview only
  python scripts/clear_stuck_incidents.py --confirm  # actually mark resolved
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true",
                        help="Actually mark incidents resolved (default: dry-run)")
    args = parser.parse_args()

    conn = sqlite3.connect(config.STATE_DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT incident_id, lifecycle_stage, created_at
          FROM incidents
         WHERE completed = 0
           AND lifecycle_stage NOT IN ('resolved')
         ORDER BY id DESC
    """).fetchall()

    if not rows:
        print("✅ No stuck incidents found.")
        conn.close()
        return

    print(f"Found {len(rows)} stuck incident(s):\n")
    for r in rows:
        print(f"  {r['incident_id']}  stage={r['lifecycle_stage']}  created={r['created_at'][:16]}")

    if not args.confirm:
        print(f"\nDry-run — pass --confirm to mark {len(rows)} incident(s) as resolved.")
        conn.close()
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE incidents
           SET lifecycle_stage = 'resolved',
               completed       = 1,
               completed_at    = ?
         WHERE completed = 0
           AND lifecycle_stage NOT IN ('resolved')
    """, (now,))
    conn.commit()
    print(f"\n✅ Marked {len(rows)} incident(s) as resolved.")
    conn.close()


if __name__ == "__main__":
    main()
