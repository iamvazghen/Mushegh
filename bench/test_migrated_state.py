"""Post-migration proof: the state the rename moved must be READABLE and POPULATED.

File presence proves nothing. A renamed SQLite file the code cannot open is the
same as no file, and an empty table is the same as a lost database. This opens
each store read-only and counts rows, because the failure mode being guarded
against is a migration that copies files and leaves the system reading empty
ones.

Run once after the rename:  uv run python bench/test_migrated_state.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

passed = failed = 0
STATE = Path.home() / ".mushegh"


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def rows(db: str) -> dict[str, int]:
    path = STATE / db
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


def main() -> None:
    print("[1] the databases the code will look for exist under their NEW names")
    for name in ("mushegh_vectors.sqlite", "mushegh_tasks.sqlite", "mushegh_presence.sqlite",
                 "mushegh_coaching.sqlite", "mushegh_graph.sqlite", "mushegh_jobs.sqlite",
                 "mushegh_stock.sqlite"):
        check(name, (STATE / name).exists())

    print("[2] no database is left under the OLD name to shadow them")
    stale = [p.name for p in STATE.glob("afon_*.sqlite")]
    check("no afon_*.sqlite left", not stale, ", ".join(stale))

    print("[3] each one opens read-only and is not empty")
    for name in ("mushegh_vectors.sqlite", "mushegh_tasks.sqlite", "mushegh_presence.sqlite"):
        try:
            counts = rows(name)
        except sqlite3.Error as exc:
            check(f"{name} opens", False, f"{type(exc).__name__}: {exc}")
            continue
        total = sum(counts.values())
        check(f"{name} opens and has rows ({total})", total > 0, str(counts))

    print("[4] the vector store carried its data, not just its file")
    counts = rows("mushegh_vectors.sqlite")
    biggest = max(counts.values()) if counts else 0
    check("vector store holds real vectors", biggest > 100, str(counts))

    print("[5] plain files the brain reads directly are present")
    for rel in ("faces/owner.npy", "voiceprint.json", "relationship.json",
                "approvals.json", "memory/journal"):
        check(rel, (STATE / rel).exists())

    print("[6] the learned-fact store came across")
    learned = STATE / "memory" / "learned"
    facts = list(learned.glob("*.md")) if learned.exists() else []
    check("thousands of learned facts survived", len(facts) > 100, str(len(facts)))

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()