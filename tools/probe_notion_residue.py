"""How much is the behavioural suite leaving in the owner's real Notion?

`notion_create_cleanup` creates a task titled `behavioral-suite-temp` and `_cleanup()`
deletes it inside `except Exception: pass` - so a failure leaves it behind silently. The
evidence that this has been happening is in a measured score: `fleet_status` answered

    "12 overdue, sir: behavioral-suite-temp (563d overdue); behavioral-suite-temp
     (195d overdue); behavioral-suite-temp (363d overdue); ..."

which is the suite reporting its own residue to the owner as his backlog.

This counts what is actually there. Read-only: it lists and nothing more.

Usage:
    python tools/probe_notion_residue.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


async def main() -> int:
    from mushegh.brain.tools.notion import notion_tasks

    result = await notion_tasks({})
    text = str(result)
    print(f"notion_tasks returned {len(text)} chars\n")

    marker = "behavioral-suite-temp"
    hits = text.count(marker)
    print(f"  occurrences of {marker!r}: {hits}")
    if hits:
        print("\n  These are test fixtures left in the owner's own Notion. The suite creates")
        print("  one per `notion_create_cleanup` run and `_cleanup` deletes it inside a bare")
        print("  `except Exception: pass`, so every failed deletion is permanent and silent.")
        print("  It is not only untidy: the residue is now reachable by the agent's own tools,")
        print("  which is how a scorecard ended up reporting it as the owner's overdue work.")
        print("\n  Fixing this needs the owner's Notion write access and their say-so - it")
        print("  means deleting real rows from their board, which is not an agent's call.")
        print("  Run with --list to print the raw rows.")
    if "--list" in sys.argv:
        print("\n" + text[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))