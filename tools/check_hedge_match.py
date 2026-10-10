"""Does `hedged()` actually match the sentence the model produced?

Inline `-c` tests get their quotes mangled by PowerShell, so this lives in a file.

The claim under test: a reply that plainly admits a limit ("I don't have the current
number of rabbits in Armenia on hand ... I can find out for you if you'd like") is
scored "overconfident" by `uncertainty.calibration`, because "i don't have" is in HEDGES
and therefore `hedged()` should return True. If that holds, the phrase is recognised and
the 40.0 has some other cause. If it does not, the lexicon misses the model's actual
wording and the scorecard is wrong about a correct answer.

Usage:
    python tools/check_hedge_match.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.shared.uncertainty import HEDGES, _clauses, calibration, hedged  # noqa: E402

REPLIES = {
    "rabbits (from the live run)":
        "I don't have the current number of rabbits in Armenia on hand, sir. "
        "However, I can find out for you if you'd like.",
    "nuclear (from the live run)":
        "Sir, nuclear power is a complex issue for Germany. Given the current energy crisis "
        "and past commitments to phase out nuclear by 2022, there's been a push for renewable "
        "energy. However, recent debates suggest a possible reconsideration of nuclear power's "
        "role. Would you like me to look into the latest developments or provide more information?",
    "weather (from the live run)":
        "To answer your question about next Tuesday in Cologne, Germany: the weather outlook "
        "for the week shows no specific rain prediction for that day, sir. It's currently "
        "forecast to be mostly dry with some cloud cover. If there's anything else you'd like "
        "to know or if you'd prefer I check again later, just let me know.",
}


def apostrophe_probe() -> None:
    """The live reply scored "overconfident"; the same sentence typed here scores "correct".

    The only difference worth testing is the apostrophe: HEDGES is written with ASCII
    U+0027, and models frequently emit the typographic U+2019. One character class would
    then silently disable the entire calibration scorer.
    """
    straight = "I don't have the current number of rabbits in Armenia on hand, sir."
    typographic = "I don’t have the current number of rabbits in Armenia on hand, sir."
    print("apostrophe probe")
    for label, sentence in (("ASCII  U+0027", straight), ("typographic U+2019", typographic)):
        print(f"  {label:20} hedged={hedged(sentence)!s:5} "
              f"calibration={calibration(sentence, unknowable=True)}")
    print()


def main() -> int:
    apostrophe_probe()
    print(f"HEDGES contains \"i don't have\": {'i don\'t have' in HEDGES}\n")
    for label, reply in REPLIES.items():
        print(label)
        print(f"  hedged(whole reply) : {hedged(reply)}")
        for clause, after_contrastive in _clauses(reply):
            print(f"    clause hedged={str(hedged(clause)):5} after_contrast={after_contrastive} "
                  f"| {clause.strip()[:78]}")
        print(f"  calibration(unknowable=True ) : {calibration(reply, unknowable=True)}")
        print(f"  calibration(unknowable=False) : {calibration(reply, unknowable=False)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())