"""Which tools are advertised every turn but routed to by nothing?

Two defects found by hand today had the same shape: `routine` and the day-planning tools
ship, are advertised on the turn, and no route reaches them - so correctness depended on
the model happening to volunteer the tool. In one case that produced a false statement
("focus mode has been deactivated" while it was still active).

That class should not need to be found by hand. This lists every core-advertised tool and
marks whether any `_ROUTES` entry can return it, separating the ones that are routed from
the ones that are merely visible.

Some are legitimately unrouted. `get_time` is the documented case: forcing it on "what
time is it" was declined as gaming the scorer, because Afon already answers that inline.
Those need to be exempt *with a reason*, or the check is just noise.

Usage:
    python tools/probe_unrouted_tools.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: Tools deliberately NOT routed, with the reason each is acceptable.
EXEMPT = {
    "get_time": "declined deliberately - Afon answers the time inline and faster than a "
                "tool round-trip; forcing it was called gaming the scorer",
}


def main() -> int:
    from afon.brain.agent import AfonAgent
    from afon.brain.intent_router import _CLAUSE_ONLY_ROUTES, _ROUTES

    agent = AfonAgent()
    core = sorted(t["function"]["name"] for t in (agent._core_tools or []))
    routed: set[str] = set()
    for _, names in _ROUTES:
        routed.update(names)
    for _, names in _CLAUSE_ONLY_ROUTES:
        routed.update(names)

    unrouted = [t for t in core if t not in routed and t not in EXEMPT]
    print(f"core-advertised tools      : {len(core)}")
    print(f"reachable by some route    : {len([t for t in core if t in routed])}")
    print(f"exempt, with a reason      : {len([t for t in core if t in EXEMPT])}")
    print(f"ROUTED BY NOTHING          : {len(unrouted)}\n")

    if unrouted:
        print("  Every one of these is on offer every turn and no route can reach it:")
        for name in unrouted:
            print(f"    {name}")
        print("\n  Not all of these are bugs - a tool may exist for the owner to name")
        print("  directly ('delete_task') rather than for the router to infer. The ones that")
        print("  matter are the ones a request implies WITHOUT naming, like `routine` was:")
        print("  'drop focus mode' implies `routine` and never says the word.")
    else:
        print("  Every core-advertised tool is either routed or exempt with a reason.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())