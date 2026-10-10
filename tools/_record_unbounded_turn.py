"""One-shot: record the 2026-10-10 unbounded-turn finding on 01.E2.

A file rather than `python -c` because the note contains quotes; inlining prose with quotes into
a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "A TURN HAS NO WALL-CLOCK BOUND. Measured 2026-10-10: with every other chain entry cooling "
    "down, a single non-streaming turn reported answered_by=minimax:MiniMax-Text-01 with "
    "latency_ms=4445344 - SEVENTY-FOUR MINUTES - and the run then hit its own one-hour limit. "
    "The log shows why it was possible rather than merely slow: _candidate_chain skipped all "
    "seven other entries as cooling-down, leaving one provider, and there was nothing left to "
    "fail over to. "
    "llm_request_timeout_seconds is 60 and it IS applied - _make_client builds "
    "AsyncOpenAI(timeout=self._timeout, max_retries=0) - but that is an httpx READ timeout, so a "
    "server that keeps dribbling bytes holds the socket open indefinitely. Worse, "
    "asyncio.wait_for appears ONLY in the two streaming paths (the first-token deadlines at "
    "llm.py:766 and llm.py:948); the non-streaming complete() path has no outer deadline at all. "
    "So a non-streaming turn can outlive any bound the operator sets, and the only reason it is "
    "normally invisible is that the chain usually has somewhere else to go. "
    "This is the 3AM property stated as a number: PRINCIPLES.md 1 promises a 90-second answer to "
    "anything that breaks, and a 74-minute turn is the failure mode that promise exists to "
    "prevent. It was found only because the provider set collapsed to one - the same collapse "
    "that made the behavioural scores unquotable - so the two findings share a cause and that "
    "cause is worth fixing either way. "
    "NOT FIXED HERE, deliberately. A turn deadline is a behaviour change on the hot LLM path, "
    "and the right bound is a judgement the owner should make: a blanket cap could truncate "
    "legitimate long work (the vault index build took 3s, but a deep research turn is not "
    "inherently short), and the correct narrow rule - shorten the bound only when the chain has "
    "collapsed to a single candidate, because hanging with nowhere to fail over to is strictly "
    "worse than failing - is still a change to when a turn is abandoned. Recorded so it is not "
    "rediscovered from a log at 3am."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py run log 2026-10-10 09:2x-10:3x, brain/llm.py",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 unbounded-turn finding recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())