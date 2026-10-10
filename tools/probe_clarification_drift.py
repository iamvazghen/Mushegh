"""Does `needs_clarification` become a false positive as calls accumulate?

The four new scenarios share a shape - `[93, 46, 46]` or `[93, 50, 50]`: first attempt
fine, every later attempt answered with `clarity_question()` verbatim at ~0.3 s and no
tool fired. The owner is asked to rephrase a request that was already clear.

If the turn assessment degrades under repeated load - a rate limit or a timeout - and a
degraded assessment reports "needs clarification", then the brain's behaviour gets worse
exactly when its provider is struggling. That would be a nasty production property: the
degraded path asks the owner a question instead of doing the work.

This repeats ONE clear request and records the assessment each time, so the trend is
visible rather than inferred from four different medians.

Usage:
    python tools/probe_clarification_drift.py [N]
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from afon.brain.judgment import JudgmentService, clarity_question  # noqa: E402

CANNED = clarity_question()
CLEAR = "Plan my day for me — two deep-work blocks and some admin, nothing past six."
CLEAR_SET = [
    "Plan my day for me — two deep-work blocks and some admin, nothing past six.",
    "Set a reminder for 7pm tonight.",
    "What's the weather in Cologne?",
    "Add milk to the shopping list.",
    "Cancel that reminder you set for 7pm.",
]


async def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    service = JudgmentService()

    print("One CLEAR request repeated, to separate drift from a stable false positive\n")
    print(f"  {CLEAR!r}\n")
    print(f"  {'#':>2}  {'assess ms':>10}  {'outcome':<14} needs_clarification")
    drift_asked = 0
    for i in range(n):
        started = time.perf_counter()
        signals = await service.assess_turn(CLEAR)
        elapsed = (time.perf_counter() - started) * 1000
        flag = signals.needs_clarification
        drift_asked += bool(flag and signals.outcome == "decided")
        mark = "   <-- would ask the owner" if flag and signals.outcome == "decided" else ""
        print(f"  {i + 1:>2}  {elapsed:>10.0f}  {signals.outcome:<14} {flag}{mark}")
    print(f"\n  {drift_asked}/{n} assessments on ONE clear request would hand the owner the")
    print("  canned question instead of planning the day.")

    print("\n\nWhich requests trigger it? Three calls each.\n")
    print(f"  {'request':<58} asked")
    for text in CLEAR_SET:
        asked = 0
        outcomes: list[str] = []
        for _ in range(3):
            signals = await service.assess_turn(text)
            outcomes.append(signals.outcome[:4])
            asked += bool(signals.needs_clarification and signals.outcome == "decided")
        flag = "  <-- false positive" if asked else ""
        print(f"  {text[:56]:<58} {asked}/3 {','.join(outcomes)}{flag}")

    # The counter-hypothesis: maybe the brain is RIGHT and the request really is
    # under-specified. "Plan my day" does not say which tasks. If making it concrete
    # clears the gate, then a scenario written this way is a badly written test, not a
    # defect in the brain - and the finding to report is about the scenario, not JEv.
    print("\n\nIs it actually ambiguous, or a real false positive?\n")
    print(f"  {'variant':<62} asked")
    variants = [
        ("as written (no tasks named)",
         "Plan my day for me — two deep-work blocks and some admin, nothing past six."),
        ("tasks named",
         "Plan my day for me — two deep-work blocks for the rabbit-farm report and one "
         "admin block to answer the accountant, nothing past six."),
        ("times named too",
         "Plan my day for me — a deep-work block at 9am for the rabbit-farm report, one "
         "at 2pm, and 30 minutes at 4pm to answer the accountant, nothing past six."),
    ]
    for label, text in variants:
        asked = 0
        for _ in range(3):
            signals = await service.assess_turn(text)
            asked += bool(signals.needs_clarification and signals.outcome == "decided")
        flag = "  <-- still asked" if asked else "  <- cleared"
        print(f"  {label:<62} {asked}/3{flag}")

    print("\n  A clear request that is refused is a worse failure than a slow one: the")
    print("  work does not happen, and the owner is implicitly blamed for being unclear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))