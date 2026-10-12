"""Are the planning tools even on offer for a fully-specified day-planning request?

`autonomy_plan` names every block, the times and the stop point, and the brain answered
with a fluent 1005-character schedule having fired NO tool. It narrated a day rather than
computing one with `plan_today` / `day_clashes` / `plan_task`.

Two candidate causes needing different fixes:
  * those tools sit in a lazy group this turn never armed, so the model was never offered
    them - a reachability gap
  * they were advertised and the model chose to narrate - a behaviour failure

This prints the routing decision, the lazy groups that light up, and whether each planner
is actually in the advertised list.

Usage:
    python tools/probe_planner_reachability.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PLANNERS = ("plan_today", "day_clashes", "plan_task")
REQUEST = ("Plan my day for me — a deep-work block at 9am for the rabbit-farm report, "
           "one at 2pm, and 30 minutes at 4pm to answer the accountant, nothing past six.")


async def main() -> int:
    from mushegh.brain.agent import MusheghAgent
    from mushegh.brain.tools import groups_for_text, groups_for_text_ranked

    agent = MusheghAgent()
    core = {t["function"]["name"] for t in (agent._core_tools or [])}

    print("Planner tools: registered, in the CORE set, and their owner group.\n")
    try:
        ranked = groups_for_text_ranked(REQUEST)
    except Exception as exc:  # noqa: BLE001
        ranked = []
        print(f"  (ranking raised {type(exc).__name__}: {exc})")
    owner_of: dict[str, str] = {}
    for entry in ranked or ():
        group = entry[0] if isinstance(entry, tuple) else entry
        for tool in PLANNERS:
            owner_of.setdefault(tool, str(group))

    for tool in PLANNERS:
        print(f"  {tool:<16} registered={tool in agent._registry}  "
              f"in_core={tool in core}  group={owner_of.get(tool, '(not routed)')}")

    print("\n  groups this text routes to:", groups_for_text(REQUEST))

    names = [t["function"]["name"] for t in agent._tools_for_turn(REQUEST)]
    print(f"\n  advertised on this turn: {len(names)} tools")
    for tool in PLANNERS:
        present = tool in names
        print(f"    {tool:<16} {'yes, index ' + str(names.index(tool)) if present else 'NO'}")

    missing = [t for t in PLANNERS if t not in names]
    print()
    if len(missing) == len(PLANNERS):
        print(f"  ALL {len(PLANNERS)} planning tools were NOT offered.")
        print("  The model could not have called them; it narrated because it had nothing")
        print("  to call. That is a reachability gap, not a behaviour failure.")
    elif missing:
        # Measured 2026-10-08: plan_today and plan_task WERE advertised (indices 42 and 3)
        # while day_clashes was not, and yet NO tool fired. So the dominant problem is
        # behaviour - the model had working tools and narrated anyway - with a secondary
        # reachability inconsistency behind it. Reporting only the missing tool would have
        # inverted which of the two actually matters, which is the mistake this tool was
        # itself corrected for.
        print(f"  {len(missing)} of {len(PLANNERS)} were not offered: {missing}")
        print("  But the others WERE: " + ", ".join(
            f"{t} (index {names.index(t)})" for t in PLANNERS if t in names) + ".")
        print("  So this is primarily a BEHAVIOUR failure - the model had working tools and")
        print("  narrated a plausible day instead - with a secondary reachability gap behind it.")
    else:
        print("  All planning tools were advertised, so the model chose to narrate rather")
        print("  than call them. That is a behaviour failure, not a reachability one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))