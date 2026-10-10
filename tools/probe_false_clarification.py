"""Is `needs_clarification` firing on requests that need no clarifying?

Two new scenarios scored 46.0 across runs 2 and 3 with the IDENTICAL reply

    "I want to get that right, sir — what exactly should I do with it?"

at 0.3 s. A real turn takes seconds, and that string is `judgment.clarity_question()`
verbatim. So the brain asked the owner to rephrase instead of doing the work.

"Is that deep dive you were running finished yet?" and "Plan my day for me — two
deep-work blocks and some admin, nothing past six." are not ambiguous. If the turn
assessment is asking about them, the gate has false positives, and the cost is the whole
turn: no tool fires and nothing gets done.

This asks JEv directly and prints what it said, alongside the replies.

Usage:
    python tools/probe_false_clarification.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from afon.brain.agent import AfonAgent  # noqa: E402
from afon.brain.judgment import JudgmentService, clarity_question  # noqa: E402

CANNED = clarity_question()

CLEAR_REQUESTS = [
    "Is that deep dive you were running finished yet?",
    "Plan my day for me — two deep-work blocks and some admin, nothing past six.",
    "You can drop focus mode now.",
    "What reminders do I actually have coming up?",
]


async def main() -> int:
    print("Does the turn assessment ask for clarity on requests that are already clear?\n")
    print(f"  the canned reply is: {CANNED!r}\n")

    service = JudgmentService()
    asked = 0
    for text in CLEAR_REQUESTS:
        signals = await service.assess_turn(text)
        agent = AfonAgent()
        agent._self_improve = False
        reply = await agent.respond(text)
        used_canned = reply.strip().startswith("I want to get that right")
        asked += used_canned
        print(f"  {text}")
        print(f"    assess outcome      : {signals.outcome}")
        print(f"    needs_clarification : {signals.needs_clarification}")
        print(f"    reply               : {reply[:110]}")
        print(f"    -> canned clarity?  : {used_canned}")
        print()

    print(f"  {asked} of {len(CLEAR_REQUESTS)} clear requests were answered with the canned")
    print("  clarifying question instead of doing the work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))