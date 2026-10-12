"""Why does the web -> memory chain fail one turn in five?

`combo_web_memory` samples [40, 93, 63, 100, 93] over five runs: a median that clears the
bar with a 40 in the sample. "Intermittent" is not a finding, so this runs the same turn
repeatedly through the live agent and, for any run that scores badly, prints the evidence
the suite would otherwise throw away - which tools actually fired, what was said, and the
scorer's own notes.

It reuses the suite's own scenario and its own scorer, so a low score here means the same
low score there. Nothing is stubbed.

Usage:
    python tools/probe_chain_flakiness.py [N]     # default 6
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "src"))

import behavioral_suite as bs  # noqa: E402


async def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else 6
    # Same guard the suite applies, for the same reason: this probe runs REAL turns and
    # `_cleanup` forgets facts in the live memory store. Added 2026-10-11 after the suite got
    # `guard_live_state` and this file — which is the tool that produced the false "zero tools"
    # finding earlier the same day — quietly kept the old behaviour. Pass --allow-live-state to
    # override.
    bs.guard_live_state("--allow-live-state" in sys.argv)

    scenario = next(s for s in bs.scenarios() if s.id == "combo_web_memory")
    turn = scenario.turns[0]

    from mushegh.brain.agent import MusheghAgent

    # Run 1 must not resume run 0's conversation. Without this the probe measures its own
    # leftovers: six runs each saw the thread where the previous turn had already answered, and
    # every one reported `tools fired: []` with median 19.0.
    print(f"session : {bs.isolate_session()}")
    print(f"turn    : {turn.say}")
    print(f"expects : {turn.expect_tools} (all={turn.all_tools})")
    print(f"text    : {turn.expect_text}")
    print(f"runs    : {runs}\n")

    # Instrument BEFORE the first agent is built, exactly as `behavioral_suite.main()` does.
    # This was missing until 2026-10-11, and it made the probe structurally incapable of
    # observing a tool call: it reads `bs._CAPTURE`, but nothing was ever writing to it,
    # so EVERY run reported `tools fired: []` and "missing tool(s)" no matter what the brain
    # actually did. Six runs scored 19.0 on that basis and it meant nothing — the instruments
    # were correct and the probe was reading a list nobody filled.
    from mushegh.brain import audit
    audit.record = bs._patched_record

    scores: list[float] = []
    for i in range(runs):
        agent = MusheghAgent()
        agent._self_improve = False
        bs._CAPTURE.clear()
        import time as _t

        t0 = _t.time()
        reply = await agent.respond(turn.say)
        elapsed = _t.time() - t0
        score, notes = bs._score_turn(turn, reply, list(bs._CAPTURE), elapsed)
        # The suite forgets its own test facts between runs (`behavioral_suite._cleanup`).
        # WITHOUT this the probe is invalid and produces a false, alarming finding: the fact
        # "Tokyo, Japan" is already in memory, the model correctly answers from it without
        # calling a tool, and the reply "I've recorded it as your next travel destination"
        # is TRUE rather than fabricated. Six runs of this probe without the cleanup looked
        # exactly like the model inventing tool use, and none of it was real.
        await bs._cleanup()
        scores.append(score)
        fired = [c["tool"] for c in bs._CAPTURE]
        flag = "  <-- LOW" if score < 90 else ""
        print(f"  run {i + 1}: {score:5.1f}{flag}")
        print(f"    tools fired : {fired}")
        print(f"    reply       : {reply[:220]}")
        for note in notes:
            print(f"    note        : {note}")
        print(f"    latency     : {elapsed:.1f}s")
        print()

    import statistics

    median = statistics.median(scores)
    low = [s for s in scores if s < 90]
    print(f"  median {median:.1f} over {runs} runs; below 90: {len(low)}")
    if low:
        print("  The runs above marked LOW are the ones worth reading - a passing median is")
        print("  not the same as a reliable turn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))