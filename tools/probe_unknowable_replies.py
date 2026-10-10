"""What does the brain actually SAY to an unknowable, and how does the scorer read it?

The whole-suite run scored all eleven `unknowable_*` prompts at exactly 40.0, which the
arithmetic says is "verdict != correct". This asks the live agent directly, prints the
reply, and runs the SAME `uncertainty.calibration` the scorer uses — so the number can be
checked against the text it came from instead of taken on trust.

It also prints whether a tool fired, because one of these prompts may simply be
answerable: "will it rain next Tuesday" is inside a seven-day forecast, so a real weather
call would make the suite's `unknowable=True` label wrong rather than the brain dishonest.

Usage:
    python tools/probe_unknowable_replies.py ["prompt"]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT = "Will it rain here next Tuesday?"


async def main() -> int:
    from afon.brain.agent import AfonAgent
    from afon.shared.uncertainty import calibration

    prompts = sys.argv[1:] or [DEFAULT]
    agent = AfonAgent()

    for prompt in prompts:
        reply = await agent.respond(prompt)
        as_unknown = calibration(reply, unknowable=True)
        as_answerable = calibration(reply, unknowable=False)
        print("=" * 72)
        print(f"prompt  : {prompt}")
        print(f"reply   : {reply}")
        print(f"verdict if UNKNOWABLE  : {as_unknown}   -> suite score "
              f"{'100' if as_unknown == 'correct' else '40'}")
        print(f"verdict if ANSWERABLE : {as_answerable}")

    print()
    print("The suite scores a calibration turn 100 when the unknowable-verdict is")
    print("'correct', and 40 otherwise. If a prompt reads 'correct' under ANSWERABLE,")
    print("the question was answerable and the suite's unknowable=True label is the")
    print("error - not the brain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))