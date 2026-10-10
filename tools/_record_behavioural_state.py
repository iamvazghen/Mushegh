"""One-shot: record the consolidated 2026-10-10 behavioural state on 01.E2.

A file rather than `python -c` because the note contains quotes and braces; inlining it into a
PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Consolidated state after the 2026-10-09/10 pass, median-3, healthy model chain, 62 scenarios "
    "scored, 0 excluded: OVERALL 89.1, up from 84.4 and from 74.5 at the start of the pass. "
    "Calibration crossed its floor for the first time: 63.5 -> 78.5 -> 87.5 -> 91.0. Web 71.5 -> "
    "84.5. Memory 65.0 -> 69.1. Combination 92.6. Channels, Safety, Honesty and Latency at 100.0. "
    "01.E2 IS NOT MET and the remaining distance is now explicit rather than assumed: eight "
    "categories still sit below 90 - Modes 88.0, Knowledge 85.4, Web 84.5, Conversation 82.0, "
    "Autonomy 79.0, Time/Utility 74.5, Memory 69.1, Fleet 59.5 - and the overall needs 95, so it is "
    "about 6 points away on top of lifting every one of those. Fleet is the lowest and is the one "
    "the owner has reserved, so it is not being touched here and its movement is not attributable "
    "to this work. "
    "What moved is worth naming, because the pattern repeated: of the failures found by widening a "
    "category past its MIN_RUNNABLE floor, a large share turned out to be the INSTRUMENT rather than "
    "the assistant - the uncertainty classifier docking three genuine admissions, the multi-intent "
    "detector calling 'and tell me' a second capability and thereby switching router narrowing off, "
    "a 402 payment failure reported to the owner as a malformed call. Two fabrications were real and "
    "were fixed at the routing layer: a journal entry that was never read, and a skills list "
    "recited from memory. What remains genuinely behavioural is the model dodging arg-bearing tool "
    "calls, which the B3 anti-fabrication stop already handles honestly rather than by pretending."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py median-3 healthy chain 2026-10-10 04:5x CEST",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 consolidated state recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())