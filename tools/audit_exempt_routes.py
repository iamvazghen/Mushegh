"""Are the tools `test_tool_reachability.py` exempts actually gaps I quietly excused?

The gate is only as honest as its EXEMPT list. Each entry claims the tool is fine
unrouted because the owner NAMES it, so nothing implies it. That claim deserves checking
rather than asserting, because two of the four tools I routed today (`routine`, and the
planner pair) were exempted-by-omission before this list existed — they were simply not
in it, because the list did not exist.

This asks the question the way an owner would, and prints whether each tool is reachable.
A tool that reads naturally but does not route is a gap hiding behind an exemption.

Usage:
    python tools/audit_exempt_routes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "src"), str(ROOT / "bench")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

#: (phrase an owner would actually say, the tool it should reach)
PROBES = [
    ("What tasks do I have?", "list_tasks"),
    ("Show me my task list.", "list_tasks"),
    ("Read my journal.", "read_journal"),
    ("What did you learn about me lately?", "read_journal"),
    ("Play some music.", "play_music"),
    ("What is playing right now?", "now_playing"),
    ("Pause it.", "media_pause"),
    ("What skills do you have?", "list_skills"),
    ("Add milk to the shopping list.", "add_task"),
    ("Save her number as Dr Who.", "save_contact"),
    ("Send myself a push.", "send_push"),
    ("What's the weather like?", "weather"),
]


def main() -> int:
    from mushegh.brain.intent_router import forced_tools

    reached, unreached = [], []
    print("Do exempted tools still get reached when a request plainly implies them?\n")
    print(f"  {'what the owner says':<40}{'tool':<18}{'routed'}")
    for phrase, tool in PROBES:
        got = forced_tools(phrase)
        ok = tool in got
        print(f"  {phrase[:38]:<40}{tool:<18}{'yes' if ok else 'NO -> ' + str(got)}")
        (reached if ok else unreached).append((phrase, tool))

    print(f"\n  reached    : {len(reached)}/{len(PROBES)}")
    print(f"  not reached: {len(unreached)}")
    if unreached:
        print("\n  These are the ones an exemption is hiding. An exemption is only honest if")
        print("  the tool really is something the owner names; if a plain request implies it,")
        print("  the exemption is a gap with a justification attached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())