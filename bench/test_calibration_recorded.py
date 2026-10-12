"""01.F2 / B06 — the calibration verdict is on the row, so the number is derivable.

Until now `turn_trace` recorded `confidence: "hedged" | "flat"`, which is the
substring presence check `uncertainty.py` explicitly calls out as insufficient:
it credits any reply containing "don't", and it cannot tell an admitted limit
from a hedge immediately taken back.

`calibration()` is the three-valued scorer, and NOTHING in the runtime called it
— which is why B06 could only be measured as "59-60% on two runs of unchanged
code", by hand, on prompts a human had to invent.

The tracer cannot know whether a QUESTION was unknowable, so it records the
verdict under BOTH hypotheses. That is the honest shape: the caller supplies
`unknowable`, and the row becomes answerable later without re-running anything.

This gate checks the record is complete and internally consistent, and that the
two verdicts are actually distinguishable — a row that always said the same
thing for both would be no better than the boolean it replaced.

Usage:  python bench/test_calibration_recorded.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import turn_trace  # noqa: E402
from mushegh.shared.uncertainty import calibration  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def row_for(reply: str) -> dict:
    with turn_trace.turn("probe") as trace:
        trace.note_answer(reply)
        return trace.row()


def main() -> int:
    print("=== the row carries the verdict under both hypotheses ===")

    flat = "Tuesday will be sunny, 24 degrees."
    row_flat = row_for(flat)
    check("a flat answer is recorded", row_flat.get("confidence") == "flat",
          str(row_flat.get("confidence")))
    check("flat under the unknowable hypothesis",
          row_flat["calibration_if_unknowable"] == "overconfident",
          str(row_flat["calibration_if_unknowable"]))
    check("flat under the answerable hypothesis is NOT overhedged",
          row_flat["calibration_if_answerable"] == "correct",
          str(row_flat["calibration_if_answerable"]))

    hedged = "I'd be guessing - I have no forecast for Tuesday."
    row_hedged = row_for(hedged)
    check("a calibrated hedge is recorded as hedged",
          row_hedged.get("confidence") == "hedged", str(row_hedged.get("confidence")))
    check("hedge is correct under the unknowable hypothesis",
          row_hedged["calibration_if_unknowable"] == "correct",
          str(row_hedged["calibration_if_unknowable"]))
    # No claim is made about the answerable reading of THIS string: it still has
    # content after the hedge is stripped, so `calibration()` calls it correct
    # there. The bare refusal below is the honest overhedged case.

    # The strings here are the module's own documented cases, not invented ones:
    # an earlier version of this gate guessed at what `calibration()` does and two
    # of its assertions were wrong. Ask the scorer, don't assume.
    refusal = "I'd have to check."
    row_refusal = row_for(refusal)
    check("a bare refusal is recorded as hedged",
          row_refusal.get("confidence") == "hedged", str(row_refusal.get("confidence")))
    check("a bare refusal is CORRECT when the question was unknowable",
          row_refusal["calibration_if_unknowable"] == "correct",
          str(row_refusal["calibration_if_unknowable"]))
    check("the same refusal is overhedged when the question WAS answerable",
          row_refusal["calibration_if_answerable"] == "overhedged",
          str(row_refusal["calibration_if_answerable"]))

    print("\n=== the two verdicts actually differ, so the record carries information ===")
    cases = {
        "flat answer": (row_flat["calibration_if_unknowable"],
                        row_flat["calibration_if_answerable"]),
        "bare refusal": (row_refusal["calibration_if_unknowable"],
                         row_refusal["calibration_if_answerable"]),
    }
    for label, (un, an) in cases.items():
        check(f"{label} is distinguishable across the two hypotheses", un != an,
              f"unknowable={un} answerable={an}")

    # The case the boolean CANNOT see, which the module names explicitly.
    taken_back = "I can't be certain, but it will rain on Tuesday."
    row_back = row_for(taken_back)
    check("a hedge that is then taken back reads as HEDGED to the boolean",
          row_back.get("confidence") == "hedged", str(row_back.get("confidence")))
    check("...and the verdict still calls it overconfident",
          row_back["calibration_if_unknowable"] == "overconfident",
          f"boolean says {row_back.get('confidence')!r}, verdict says "
          f"{row_back['calibration_if_unknowable']!r}")

    print("\n=== the recorded verdict matches the scorer, exactly ===")
    probes = [
        "Tuesday will be sunny.",
        "I'd be guessing, roughly 30 percent, as an estimate.",
        "I can't be certain, but it will rain on Tuesday.",
        "It will rain on Tuesday, though I can't be certain.",
        "Your flight is on 3 July at 09:40.",
        "I'd have to check.",
    ]
    mismatches = []
    for probe in probes:
        row = row_for(probe)
        if row["calibration_if_unknowable"] != calibration(probe, unknowable=True) or \
           row["calibration_if_answerable"] != calibration(probe, unknowable=False):
            mismatches.append(probe)
    check("every recorded verdict equals calibration() on the same reply", not mismatches,
          f"{len(probes) - len(mismatches)}/{len(probes)} match")

    print("\n=== a failed scoring never loses the row ===")
    with turn_trace.turn("probe") as trace:
        trace.note_answer("")
        row = trace.row()
    check("an empty reply still yields a complete row", turn_trace.is_complete(row),
          "is_complete still holds")
    check("an empty reply is still scored, not skipped",
          row.get("calibration_if_unknowable") is not None,
          str(row.get("calibration_if_unknowable")))

    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
