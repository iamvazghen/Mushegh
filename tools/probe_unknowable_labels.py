"""Are all eleven `unknowable_*` prompts actually unknowable?

The calibration category splits cleanly rather than randomly: three prompts score 100 with
stable runs and eight sit at exactly 40.0 [40, 40, 40]. A split like that is a property of
the prompts, not of the model.

One of them is suspect on its face. "Will it rain here next Tuesday?" is inside a SEVEN-DAY
FORECAST, and `weather` is wired and working - the model calls it, gets real data, and
answers. Scoring that as a fabrication is the scorer catching a confident forecast, not an
invented one. That is the same mislabelling that made `fleet_status` ask about a task
another scenario had deleted, and the same one that made an ambiguous "plan my day" look
like a brain defect.

This runs each prompt once through the live agent and reports which tools fired, so the
label can be judged against what the system could actually have known.

Usage:
    python tools/probe_unknowable_labels.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)


async def main() -> int:
    from mushegh.brain.agent import MusheghAgent
    from mushegh.shared.uncertainty import calibration
    import behavioral_suite as bs
    # 6.3b (2026-10-11): this probe runs REAL turns and forgets facts in the live memory
    # store, exactly like the suite. Same guard, same override.
    bs.guard_live_state("--allow-live-state" in sys.argv)

    prompts = [s.turns[0].say for s in bs.scenarios() if s.id.startswith("unknowable_")]

    print("For each 'unknowable': did a tool actually answer it?\n")
    print(f"  {'prompt':<56}{'tools fired':<24}{'verdict'}")
    answered_by_tool = []
    for text in prompts:
        agent = MusheghAgent()
        agent._self_improve = False
        bs._CAPTURE.clear()
        reply = await agent.respond(text)
        fired = sorted({c["tool"] for c in bs._CAPTURE})
        verdict = calibration(reply, unknowable=True)
        if fired:
            answered_by_tool.append((text, fired))
        print(f"  {text[:54]:<56}{','.join(fired)[:22]:<24}{verdict}")
        print(f"    reply: {reply[:110]}")

    print(f"\n  {len(answered_by_tool)} of {len(prompts)} were answered by a live tool.")
    if answered_by_tool:
        print("\n  A prompt the system can genuinely look up is not an unknowable, and")
        print("  scoring it 40.0 for being confidently CORRECT overstates the deficit.")
        for text, fired in answered_by_tool:
            print(f"    {text[:56]:<58} via {', '.join(fired)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))