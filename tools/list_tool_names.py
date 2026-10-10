"""List the tool names the registry actually exposes, so new scenarios cannot name a tool
that does not exist.

Writing a second scenario into each of the nine thin categories would raise every one to
the `MIN_RUNNABLE_PER_CATEGORY` floor and take the overall from 8 of 17 categories to 17
of 17. That is only worth doing if the scenarios reference tools that really exist: a
scenario naming `cancel_reminder` when the registry says `delete_reminder` can never pass,
and a category that can never pass is worse than one honestly excluded as thin.

Usage:
    python tools/list_tool_names.py [filter]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.brain.agent import AfonAgent  # noqa: E402


def main() -> int:
    agent = AfonAgent()
    names = sorted(agent._registry)
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if needle:
        names = [n for n in names if needle in n]
    print(f"{len(names)} tool(s) in the registry"
          + (f" matching {needle!r}" if needle else ""))
    for name in names:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())