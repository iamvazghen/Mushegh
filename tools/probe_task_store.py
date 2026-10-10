"""How much has the behavioural suite left in the owner's real task store?

`bench/test_no_result_sentinels.py` asks `task_status({"query": "zzz-nonexistent"})` for a
complete negative and gets 43 tasks back instead - "Eggs", "buy bread", "Coffee",
"Add milk to shopping list", repeated. Two things are entangled here and this separates
them: how big the store is, and whether the query filter is honoured at all.

Read-only: it counts and groups, and deletes nothing.

Usage:
    python tools/probe_task_store.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(os.path.expanduser("~")) / ".afon" / "afon_tasks.sqlite"


def main() -> int:
    if not DB.is_file():
        print(f"  no task store at {DB}")
        return 0
    conn = sqlite3.connect(DB)
    tables = [r[0] for r in conn.execute(
        "select name from sqlite_master where type='table'")]
    print(f"  {DB}  ({DB.stat().st_size} bytes)\n")
    for table in tables:
        cols = [c[1] for c in conn.execute(f"pragma table_info({table})")]
        count = conn.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  {table}: {count} rows   columns={cols}")
        text_col = next((c for c in ("text", "title", "what", "task", "subject")
                         if c in cols), None)
        if count and text_col:
            values = [r[0] for r in conn.execute(
                f"select {text_col} from {table} where {text_col} is not null")]
            counts = Counter(v.strip().lower() for v in values)
            print(f"    distinct texts: {len(counts)}")
            for name, n in counts.most_common(8):
                print(f"      {n:>3}x  {name[:52]}")

        # Is the pollution from today, or long-standing? Attribution matters: a suite
        # that litters the owner's live database is a different problem from one that
        # has always left it.
        if "started_at" in cols:
            rows = list(conn.execute(
                f"select substr(coalesce(started_at,''),1,10) as d, count(*) "
                f"from {table} group by d order by d desc limit 10"))
            print("\n    rows by day (started_at):")
            for day, n in rows:
                print(f"      {day or '(none)':<14} {n}")
        if "title" in cols and "status" in cols:
            rows = list(conn.execute(
                f"select status, count(*) from {table} group by status order by 2 desc"))
            print("\n    rows by status:")
            for status, n in rows:
                print(f"      {status:<14} {n}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())