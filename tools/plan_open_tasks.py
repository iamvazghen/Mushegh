"""List the tasks a subsystem still owes, straight from the execution registry.

`docs/systems-plan.json` is the source of truth; `docs/SYSTEMS.md` renders it. The
one thing the rendered dashboard does NOT carry is the per-task detail — which
tasks are still open, what gate each one is judged by, and what evidence already
exists against it. That is what this prints.

Reading it matters before touching S01, because the registry state and the
evidence underneath it drift apart: a task can sit at `open` while its own
evidence records the bar as met (01.E1 does), and a gate can be cited twice with
different numbers because one citation names the whole file and the other names
one numbered section (01.R7 cites all of test_jev_turn_assessment, 01.R8 cites
section [3]) — which looks like lost assertions and is not.

Usage:
    python tools/plan_open_tasks.py                 # every unfinished task
    python tools/plan_open_tasks.py S01             # one subsystem
    python tools/plan_open_tasks.py S01 --evidence  # include evidence notes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "systems-plan.json"

DONE_STATES = {"done", "complete", "completed"}


def load() -> list[dict]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    return plan["systems"]


def unfinished(system: dict) -> list[dict]:
    return [t for t in (system.get("tasks") or []) if str(t.get("state")) not in DONE_STATES]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system", nargs="?", help="system id, e.g. S01 (default: all)")
    ap.add_argument("--evidence", action="store_true", help="print evidence notes")
    args = ap.parse_args(argv)

    systems = load()
    if args.system:
        wanted = args.system.upper()
        systems = [s for s in systems if str(s.get("id", "")).upper() == wanted]
        if not systems:
            print(f"no system {wanted!r}; ids look like S01..S50", file=sys.stderr)
            return 1

    total = 0
    for s in systems:
        todo = unfinished(s)
        if not todo:
            continue
        print(f"\n{s['id']} — {s.get('title', '')}   ({len(todo)} unfinished)")
        for t in todo:
            total += 1
            print(f"  {t['id']:<7} [{t.get('state')}] tier={t.get('tier')}")
            print(f"      {t.get('title', '')}")
            if t.get("gate"):
                print(f"      gate: {t['gate']}")
            if t.get("tests"):
                print(f"      tests: {', '.join(t['tests'])}")
            if args.evidence:
                for e in t.get("evidence") or []:
                    if isinstance(e, dict):
                        print(f"      - {e.get('date')} [{e.get('kind')}] {e.get('note', '')}")
                    else:
                        print(f"      - {e}")
            print()

    print(f"{total} unfinished task(s) across {len(systems)} subsystem(s).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())