"""One-shot: record the 2026-10-10 coverage-floor and Modes-duplication findings on 01.E2.

A file rather than `python -c` because the note contains quotes; inlining prose with quotes into
a PowerShell here-string mangles them.
"""

import json

PATH = "docs/systems-plan.json"

NOTE = (
    "Two measurement-shape findings, found while chasing why the Modes category swung 96.5 to "
    "73.0 to 46.0 across three runs with one-turn changes in between. "
    "FIRST, Modes had exactly two scenarios and BOTH began with the same sentence: mode_clear "
    "opens with 'put yourself in focus mode' because an earlier version assumed a mode was "
    "already on, and with cleanup now running per RUN that assumption is guaranteed false. Legit "
    "as setup for a clear-test, but it meant the category could only ever measure one mode. A "
    "third scenario was added, mode_lockdown, which is a different mode with different words - "
    "so Modes now measures focus AND lockdown rather than focus twice. "
    "SECOND, and larger: MIN_RUNNABLE_PER_CATEGORY is 2, and TWELVE OF THE SEVENTEEN categories "
    "sit exactly on that floor - Autonomy, Conversation, Fleet, Honesty, Knowledge, Latency, "
    "Memory, Multi-Device, Proactivity, Safety, Tasks and Web. A category at the floor that "
    "loses ONE scenario, to a credential going away or a scenario erroring, is EXCLUDED "
    "ENTIRELY from the scorecard: not scored low, dropped. That is not hypothetical, it is how "
    "Combination vanished from production-readiness once before. Calibration is the only "
    "well-covered category by design at 24 scenarios, which is also why a single classifier "
    "false positive moved 40% of the overall score. The Combination category was taken from 2 to "
    "5 earlier the same session for exactly this reason; the other eleven at the floor remain "
    "one scenario away from disappearing, and that is the honest shape of the evidence rather "
    "than a set of eleven verified categories."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as fh:
        plan = json.load(fh)

    s01 = next(s for s in plan["systems"] if s["id"] == "S01")
    e2 = next(t for t in s01["tasks"] if t["id"] == "01.E2")
    e2.setdefault("evidence", []).append({
        "kind": "recorded-note",
        "source": "bench/behavioral_suite.py scenario inventory 2026-10-10",
        "note": NOTE,
    })

    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    print("01.E2 coverage-floor finding recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())