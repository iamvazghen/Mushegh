"""Should the B6 clause router already have forced a tool on the day-planning request?

`autonomy_plan` had `plan_today` and `plan_task` advertised, fired neither, and narrated a
1005-character schedule. The codebase already has machinery aimed at exactly this: the
clause router builds a per-clause plan, and a completion pass forces a tool the model has
not used. So the question is whether that machinery *should* have fired here.

  * `clause_tools` returns the planner tools -> B6 should have forced one, and its failure
    to do so is a defect in the forcing path
  * `clause_tools` returns nothing -> the router does not recognise "plan my day" at all,
    which is a routing gap rather than a forcing bug, and a different fix

Both are worth knowing and only one of them is true.

Usage:
    python tools/probe_clause_plan_for_planning.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.intent_router import clause_tools, forced_tools  # noqa: E402

CASES = [
    ("the failing scenario",
     "Plan my day for me — a deep-work block at 9am for the rabbit-farm report, one at "
     "2pm, and 30 minutes at 4pm to answer the accountant, nothing past six."),
    ("plainer phrasing",
     "Plan my day for me."),
    ("an adjacent case that works",
     "Look up the capital of Japan and remember it as my next travel destination."),
    ("a single-tool phrasing",
     "Remind me to stretch in 90 minutes."),
]


def main() -> int:
    print("Does the clause router see a planning request as tool-shaped?\n")
    print(f"  {'case':<28}{'clause_tools':<34}{'forced_tools'}")
    for label, text in CASES:
        print(f"  {label:<28}{str(clause_tools(text)):<34}{forced_tools(text)}")

    planning = CASES[0][1]
    plan = clause_tools(planning)
    print()
    if plan:
        print(f"  The router DID produce a plan for the failing scenario: {plan}")
        print("  So the completion pass should have had something to force, and not forcing")
        print("  it is a defect in the forcing path rather than a missing route.")
    else:
        print("  The router produced NO plan for the failing scenario.")
        print("  So B6 had nothing to force: this is a routing gap - the router does not")
        print("  recognise a planning request as tool-shaped - not a bug in the forcing path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())