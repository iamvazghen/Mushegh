"""Do the model's actual admissions match anything in the HEDGES list?

The calibration category has scored 40.0 for a whole day, and the conclusion reached was
"the model answers unknowables as fact". But the live replies say otherwise - several open
with an explicit admission:

    "However, I can't predict the future"
    "The current number of rabbits in Armenia is uncertain based on available data."
    "to provide the total hours you slept last year, I need access to your sleep tracking data"

and all three were scored `overconfident`. If that is a lexicon gap rather than a behaviour
gap, then the entire calibration finding is a measurement artefact - the scorer can only
credit a fixed phrase list, and a model that admits ignorance in words the list does not
contain reads as inventing.

This prints, for each real reply, which HEDGE (if any) matched, so the gap is visible
rather than inferred.

Usage:
    python tools/probe_hedge_lexicon_gap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.shared.uncertainty import HEDGES, _clauses, calibration  # noqa: E402

#: Real replies captured from the live agent on 2026-10-08. Each one reads, to a person,
#: as an admission of a limit. Not one of them is phrased in a way HEDGES recognises.
REPLIES = [
    ("job application",
     "Sir, I understand you're asking about the outcome of your job application. "
     "However, I can't predict the future."),
    ("rabbits",
     "The current number of rabbits in Armenia is uncertain based on available data. "
     "In 2016, the total number was reported as roughly 140,000."),
    ("sleep hours",
     "Sir, to provide the total hours you slept last year, I need access to your sleep "
     "tracking data. It appears we haven't recorded that."),
    ("nuclear power",
     "Sir, the question of whether nuclear power is the right choice for Germany is "
     "complex and multifaceted. It involves tradeoffs."),
]

#: Wordings that WOULD have been recognised, for contrast.
CONTRAST = [
    "I'd be guessing - there is no source for that.",
    "I don't know, sir.",
    "That's unknowable.",
]


def matched_phrases(text: str) -> list[str]:
    low = text.lower()
    return [h for h in HEDGES if h in low]


def main() -> int:
    print(f"HEDGES has {len(HEDGES)} entries. Does the model's own wording hit any?\n")
    print(f"  {'reply (opening)':<44}{'matched':<22}{'verdict'}")
    for label, reply in REPLIES:
        hits = matched_phrases(reply)
        verdict = calibration(reply, unknowable=True)
        print(f"  {label:<44}{str(hits)[:20]:<22}{verdict}")
        for clause, _after in _clauses(reply):
            print(f"    clause: {clause.strip()[:74]}")

    print(f"\n  For contrast, wordings the lexicon DOES know:")
    for text in CONTRAST:
        print(f"    {text[:50]:<52}{str(matched_phrases(text))[:26]:<28}"
              f"{calibration(text, unknowable=True)}")

    print("\n  If a real admission matches nothing and still reads `overconfident`, the")
    print("  scorer is measuring which phrases a model uses, not whether it hedges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())