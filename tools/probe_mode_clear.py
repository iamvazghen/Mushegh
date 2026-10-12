"""Does dropping focus mode actually drop it?

`mode_clear` scores 50.0 with runs `[50.0, 50.0, 50.0]` — a perfectly stable failure —
and the reply is "Focus mode has been deactivated, sir. You're back to normal operation."
with **no `routine` tool fired**.

A score is one thing. A turn that tells the owner a mode has changed when it has not is a
correctness problem: he goes back to work expecting to be interrupted and is not, or
believes he is protected and is not. This checks the state, not the sentence.

Usage:
    python tools/probe_mode_clear.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


async def main() -> int:
    from mushegh.brain.agent import MusheghAgent
    from mushegh.brain.modes import MODES

    agent = MusheghAgent()
    agent._self_improve = False

    print("Does the turn that says 'focus mode is off' actually turn it off?\n")

    MODES.clear()
    MODES.set_focus(30)
    print(f"  before : focus_active={MODES.focus_active()}   status={MODES.status()!r}")

    reply = await agent.respond("You can drop focus mode now.")
    after = MODES.focus_active()
    print(f"  reply  : {reply[:120]}")
    print(f"  after  : focus_active={after}   status={MODES.status()!r}\n")

    claimed_off = "focus" in reply.lower() and any(
        w in reply.lower() for w in ("deactivated", "cleared", "off", "normal", "back")
    )
    print(f"  the reply claims focus mode is off : {claimed_off}")
    print(f"  focus mode is actually off        : {not after}")
    if claimed_off and after:
        print("\n  THE REPLY IS FALSE. Mushegh says he has dropped a mode and has not, so the")
        print("  owner's expectation of being uninterrupted does not match reality.")
        print("  That is a correctness bug, not a score.")
    elif not claimed_off and after:
        print("\n  He did not claim to have changed it, and it did not change - consistent,")
        print("  though it means 'drop focus mode' reached no tool at all.")
    else:
        print("\n  The mode really was cleared.")
    MODES.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))